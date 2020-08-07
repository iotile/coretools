# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.
"""This file contains necessary functionality to manage the hardware"""

import time
import binascii
import logging
from queue import Empty
from typedargs.annotate import annotated, param, return_type, finalizer, docannotate, context

from iotile.core.dev.semver import SemanticVersion, SemanticVersionRange
from iotile.core.hw.exceptions import UnknownModuleTypeError
from iotile.core.exceptions import ArgumentError, HardwareError, ValidationError, TimeoutExpiredError, ExternalError
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.hw.transport.adapterstream import AdapterStream
from iotile.core.dev.config import ConfigManager
from iotile.core.hw.debug import DebugManager
from iotile.core.utilities.linebuffer_ui import LinebufferUI
from iotile.core.utilities.gid import uuid_to_slug

from .proxy import TileBusProxyObject
from .app import IOTileApp


@context("HardwareManager")
class HardwareManager:
    """
    A module for managing and interacting with IOTile Hardware

    This context provides tools to configure, control, debug and program
    any IOTile module.  Specific functionality can be implemented in dynamically
    loaded proxy objects that are designed to provide access to each IOTile.

    To create a HardwareManager, you need to pass a port string that describes the
    method to be used to connect to the IOTile device. The method should specify the
    name of the connection method optionally followed by a colon and any extra information
    possibly needed to connect using that method.

    Currently implemented ports are:
        bled112
        jlink
        jlink:mux=ftdi
        virtual:...(e.g. simple)
    """

    logger = logging.getLogger(__name__)

    @param("port", "string", desc="transport method to use in the format transport[:port]")
    @param("record", "path", desc="Optional file to record all RPC calls and responses made on this HardwareManager")
    def __init__(self, port=None, record=None, adapter=None):
        if port is None and adapter is None:
            try:
                conf = ConfigManager()
                port = conf.get('core:default-port')
            except ArgumentError:
                raise ArgumentError("No port given and no core:default-port config variable set",
                                    suggestion="Specify the port to use to connect to the IOTile devices")
        elif port is None:
            port = ""

        transport, _, arg = port.partition(':')

        self.transport = transport
        self.port = None
        if arg != "":
            self.port = arg


        self.stream = self._create_stream(adapter, record=record)

        self._stream_queue = None
        self._trace_queue = None
        self._broadcast_queue = None
        self._trace_data = bytearray()

        self._proxies = {'TileBusProxyObject': TileBusProxyObject}
        self._name_map = {TileBusProxyObject.ModuleName(): [TileBusProxyObject]}

        self._known_apps = {}
        self._named_apps = {}

        self._setup_proxies()
        self._setup_apps()

    def _setup_proxies(self):
        """Load in proxy module objects for all of the registered components on this system."""

        # Find all of the registered IOTile components and see if we need to add any proxies for them
        reg = ComponentRegistry()
        proxy_classes = reg.load_extensions('iotile.proxy', class_filter=TileBusProxyObject, product_name="proxy_module")

        for name, obj in proxy_classes:
            proxy_key = obj.__name__ + ':' + name

            # awu_10/01/19 - we want to add all proxies even if duplicate but diff version
            # if proxy_key in self._proxies:
            #     continue

            self._proxies[proxy_key] = obj

            # Check if this object matches a specific shortened name so that we can
            # automatically match a hw module to a proxy without user intervention
            try:
                short_name = obj.ModuleName()
                if short_name in self._name_map:
                    self._name_map[short_name].append(obj)
                else:
                    self._name_map[short_name] = [obj]
            except Exception:  # pylint: disable=broad-except;
                # We don't want this to die if someone loads a misbehaving plugin
                self.logger.exception("Error importing misbehaving proxy object %s, skipping.", obj)

    def _setup_apps(self):
        """Load in all iotile app objects for all registered or installed components on this system."""

        reg = ComponentRegistry()
        app_classes = reg.load_extensions('iotile.app', class_filter=IOTileApp, product_name="app_module")

        for _name, app in app_classes:
            try:
                matches = app.MatchInfo()
                name = app.AppName()
                for tag, ver_range, quality in matches:
                    if tag not in self._known_apps:
                        self._known_apps[tag] = []

                    self._known_apps[tag].append((ver_range, quality, app))

                if name in self._named_apps:
                    self.logger.warning("Added an app module with an existing name, overriding previous app, name=%s",
                                        name)

                self._named_apps[name] = app
            except Exception:  #pylint: disable=broad-except;
                # We don't want this to die if someone loads a misbehaving plugin
                self.logger.exception("Error importing misbehaving app module %s, skipping.", app)

    @param("address", "integer", "positive", desc="numerical address of module to get")
    @param("basic", "bool", desc="return a basic global proxy rather than a specialized one")
    @param("force", "str", desc="Explicitly set the 6-character ID to match against")
    @param("uuid", "integer", desc="UUID of the device we would like to connect to")
    def get(self, address, basic=False, force=None, uuid=None):
        """Create a proxy object for a tile by address.

        The correct proxy object is determined by asking the tile for its
        status information and looking up the appropriate proxy in our list of
        installed proxy objects.  If you want to send raw RPCs, you can get a
        basic TileBusProxyObject by passing basic=True.
        """

        if basic is True and force is not None:
            raise ArgumentError("You cannot conbine basic and force, they have opposite effects")

        if force is not None and len(force) != 6:
            raise ArgumentError("You must specify a 6 character name when using the force parameter", force=force)

        if uuid is not None:
            self.connect(uuid)

        tile = self._create_proxy('TileBusProxyObject', address)

        if basic:
            return tile

        name = tile.tile_name()
        version = tile.tile_version()

        if force is not None:
            name = force

        # Now create the appropriate proxy object based on the name and version of the tile
        tile_type = self.get_proxy(name, version)
        if tile_type is None:
            raise HardwareError("Could not find proxy object for tile", name="'{}'".format(name),
                                known_names=self._name_map.keys())

        tile = tile_type(self.stream, address)
        tile._hwmanager = self

        return tile

    @docannotate
    def app(self, name=None, path=None, uuid=None):
        """Find the best IOTileApp for the device we are connected to.

        Apps are matched by looking at the app tag and version information
        specified by the connected device.  If no installed app matches, an
        exception will be thrown.  You can also force the matching of a
        specific app by using the name parameter.

        Args:
            name (str): Optional name of the app that you wish to load.
            path (str): Optional path to a python file containing the
                app that you wish to load.
            uuid (int): Optional uuid of device to directly connect to.
                Passing this parameter is equivalent to calling ``connect``
                before calling this method

        Returns:
            IOTileApp show-as context: The IOTileApp class that was loaded
                for this device.
        """

        if name is not None and path is not None:
            raise ArgumentError("You cannot specify both an app name and an app path", name=name, path=path)

        if uuid is not None:
            self.connect(uuid)

        # We perform all app matching by asking the device's controller for its app and os info
        tile = self._create_proxy('TileBusProxyObject', 8)
        device_id, os_info, app_info = tile.rpc(0x10, 0x08, result_format="L8xLL")

        os_tag = os_info & ((1 << 20) - 1)
        os_version_str = '%d.%d.%d' % ((os_info >> 26) & ((1 << 6) - 1), (os_info >> 20) & ((1 << 6) - 1), 0)

        app_tag = app_info & ((1 << 20) - 1)
        app_version_str = '%d.%d.%d' % ((app_info >> 26) & ((1 << 6) - 1), (app_info >> 20) & ((1 << 6) - 1), 0)

        os_version = SemanticVersion.FromString(os_version_str)
        app_version = SemanticVersion.FromString(app_version_str)

        app_class = None

        # If name includes a .py, assume that it points to python file and try to load that.
        if name is None and path is not None:
            _name, app_class = ComponentRegistry().load_extension(path, class_filter=IOTileApp, unique=True)
        elif name is not None:
            app_class = self._named_apps.get(name)
        else:
            best_match = None
            matching_tags = self._known_apps.get(app_tag, [])

            for (ver_range, quality, app) in matching_tags:
                if ver_range.check(app_version):
                    if best_match is None:
                        best_match = (quality, app)
                    elif quality > best_match[0]:
                        best_match = (quality, app)

            if best_match is not None:
                app_class = best_match[1]

        if app_class is None:
            raise HardwareError("Could not find matching application for device", app_tag=app_tag, explicit_app=name,
                                installed_apps=[x for x in self._named_apps])

        app = app_class(self, (app_tag, app_version), (os_tag, os_version), device_id)
        return app

    @param("uuid", "integer", desc="UUID of the device we would like to connect to")
    def controller(self, uuid=None):
        """Find an attached IOTile controller and attempt to connect to it."""

        if uuid is not None:
            self.connect(uuid)

        return self.get(8)

    @param("device_uuid", "integer", desc="UUID of the device we would like to connect to")
    @param("wait", "float", desc="Time to wait for devices to show up before connecting")
    def connect(self, device_uuid, wait=None):
        """Attempt to connect to a device by its UUID"""

        self.stream.connect(device_uuid, wait=wait)

    @param("connection_string", "string", desc="opaque connection string indicating which device")
    def connect_direct(self, connection_string):
        """Attempt to connect to a device using a connection string"""

        self.stream.connect_direct(connection_string)

    @annotated
    def disconnect(self):
        """Attempt to disconnect from a device."""

        self._trace_queue = None
        self._stream_queue = None

        self.stream.disconnect()

    @param("connection_string", "string", desc="opaque connection string indicating which device")
    def debug(self, connection_string=None):
        """Prepare the device for debugging if supported.

        Some transport mechanisms support a low level debug channel that
        permits recovery and test operations such as erasing and forcibly
        reprogramming a device or dumping memory.

        If no debug operations are supported, this function will raise an
        exception.

        If you pass a connection_string to this method to force a connection
        to a device directly, it will be opened without the RPC interface
        being opened.  If you need to subsequently send RPCs after performing
        the debug actions, you will need to disconnect from the device and
        reconnect normally (using ``connect`` or ``connect_direct``) first.
        """

        if connection_string is not None:
            self.stream.connect_direct(connection_string, no_rpc=True)

        self.stream.enable_debug()
        return DebugManager(self.stream)

    @return_type("bool")
    def heartbeat(self):
        """Check if we still have a connection to the DeviceAdapter."""

        result = self.stream.debug_command('heartbeat')
        return result.get('alive')

    @annotated
    def enable_broadcasting(self):
        """Enable the collection of broadcast IOTile reports.

        Broadcast reports contain tagged readings from an IOTile device
        but are sent without a connection to that device.  The specific
        method that is used to broadcast the report varies by connection
        technology but it could be, e.g., a bluetooth low energy advertising
        packet.

        By default all broadcast reports are dropped unless you call
        enable_broadcasting to allocate a queue to receive them.

        There does not need to be an active connection for you to call
        enable_broadcasting.

        Once you call enable_broadcasting, it remains in effect for the
        duration of this HardwareManager object.
        """

        self._broadcast_queue = self.stream.enable_broadcasting()

    @annotated
    def enable_streaming(self):
        """Enable streaming of report data from the connected device.

        This function will create an internal queue to receive and store
        reports until the user looks at them and then inform the connected
        IOTile device that is should begin streaming data.

        This is done by telling the underlying DeviceAdapter managing the
        communication with the device that it should open the device's
        streaming interface.

        There is currently no way to close the streaming interface except
        by disconnecting from the device and then reconnecting to it.
        """

        self._stream_queue = self.stream.enable_streaming()

    @annotated
    def enable_tracing(self):
        """Enable tracing of realtime debug information over this interface."""

        self._trace_queue = self.stream.enable_tracing()

    @return_type("integer")
    def count_reports(self):
        """Return the current size of the reports queue"""

        if self._stream_queue is None:
            return 0

        return self._stream_queue.qsize()

    @docannotate
    def watch_broadcasts(self, whitelist=None, blacklist=None):
        """Spawn an interactive terminal UI to watch broadcast data from devices.

        Devices are allowed to post a broadcast report containing stream data.
        This function will create a list in your console window with the latest
        broadcast value from each device in range.

        Args:
            whitelist (list(integer)): Only include devices with these listed ids.
            blacklist (list(integer)): Include every device **except** those with these
                specific ids.  If combined with whitelist, whitelist wins and this
                parameter has no effect.
        """

        title = "Watching Broadcast Reports (Ctrl-C to Stop)"
        subtitle = ""
        if self.transport == 'bled112':
            reg = ConfigManager()
            if not reg.get('bled112:active-scan'):
                subtitle = "Active Scanning not active, you won't see v1 broadcasts"

        if whitelist is not None:
            whitelist = set(whitelist)

        if blacklist is not None:
            blacklist = set(blacklist)

        def _title(_items):
            return [title, subtitle]

        def _poll():
            results = [x for x in self.iter_broadcast_reports(blocking=False)]
            return results

        def _text(item):
            fmt_uuid = "%08X" % item.origin
            fmt_uuid = fmt_uuid[:4] + '-' + fmt_uuid[4:]

            reading = item.visible_readings[0]
            return "{0: <15} stream: {1: 04X}    value: {2: <8}".format(fmt_uuid, reading.stream, reading.value)

        def _sort_order(item):
            return item.origin

        def _hash(item):
            uuid = item.origin
            stream_id = item.visible_readings[0].stream
            if whitelist is not None and uuid not in whitelist:
                return None

            if blacklist is not None and whitelist is None and uuid in blacklist:
                return None

            item_id = str(uuid) + "," + str(stream_id)
            return item_id

        line_ui = LinebufferUI(_poll, _hash, _text, sortkey_func=_sort_order, title=_title)
        line_ui.run()

    @docannotate
    def watch_scan(self, whitelist=None, blacklist=None, sort="id"):
        """Spawn an interactive terminal UI to watch scan results.

        This is just a fancy way of calling scan() repeatedly and
        deduplicating results per device so that each one has a static place
        on the screen.

        You can decide how you want to order the results with the sort parameter.

        If you pick "id", the default, then results will have a largely static
        order based on the UUID of each device so that there will not be too
        much screen churn.

        Args:
            whitelist (list(integer)): Only include devices with these listed ids.
            blacklist (list(integer)): Include every device **except** those with these
                specific ids.  If combined with whitelist, whitelist wins and this
                parameter has no effect.
            sort (str): The specific way to sort the list on the screen.  Options are
                id, signal.  Defaults to id.
        """

        if whitelist is not None:
            whitelist = set(whitelist)

        if blacklist is not None:
            blacklist = set(blacklist)

        def _title(items):
            return ["Realtime Scan: %d Devices in Range" % len(items)]

        def _poll():
            return self.scan()

        def _text(item):
            fmt_uuid = "%08X" % item['uuid']
            fmt_uuid = fmt_uuid[:4] + '-' + fmt_uuid[4:]

            return "{0: <15} signal: {1: <7d} connected: {2: <8}".format(fmt_uuid, item['signal_strength'],
                                                                         str(item.get('user_connected', 'unk')))

        def _sort_order(item):
            if sort == "signal":
                return -item['signal_strength']

            return item['uuid']

        def _hash(item):
            uuid = item['uuid']
            if whitelist is not None and uuid not in whitelist:
                return None

            if blacklist is not None and whitelist is None and uuid in blacklist:
                return None

            return uuid

        line_ui = LinebufferUI(_poll, _hash, _text, sortkey_func=_sort_order, title=_title)
        line_ui.run()

    @docannotate
    def watch_reports(self, whitelist=None, blacklist=None):
        """Spawn an interactive terminal UI to watch reports once connected to a device.

        Args:
            whitelist (list(integer)): Only include streams with these listed ids.
            blacklist (list(integer)): Include every stream **except** those with these
                specific ids.  If combined with whitelist, whitelist wins and this
                parameter has no effect.
        """

        if whitelist is not None:
            whitelist = set(whitelist)

        if blacklist is not None:
            blacklist = set(blacklist)

        def _title(items):
            base = "Watching Report for Device ID "
            if items:
                base = base + str(items[list(items.keys())[0]].object.origin)
            meta = "{:15s} {:4s}  {:8s}".format("Last Timestamp", "Stream ID", "Stream Value")
            return [base, meta]

        def _poll():
            results = [x for x in self.iter_reports(blocking=False)]
            return results

        def _text(item):
            reading = item.visible_readings[0]
            return "{0:<15} {1:04X}         value: {2:<8}".format(reading.raw_time, reading.stream, reading.value)

        def _sort_order(item):
            return item.origin

        def _hash(item):
            stream = item.visible_readings[0].stream

            if whitelist is not None and stream not in whitelist:
                return None

            if blacklist is not None and whitelist is None and stream in blacklist:
                return None

            return stream

        if not self.stream.connected:
            print("Not connected to a device. Please connect first")
            return

        if not self._stream_queue:
            print("Enable streaming to watch reports")
            return

        line_ui = LinebufferUI(_poll, _hash, _text, sortkey_func=_sort_order, title=_title)
        line_ui.run()

    @return_type("string")
    @param("encoding", "string", desc="The encoding to use to dump the trace, either 'hex' or 'raw'")
    def dump_trace(self, encoding):
        """Dump all received tracing data currently received from the device to stdout

        The data is encoded per the encoding parmeter which must be either
        the string 'hex' or 'raw'.  If hex is passed, the data is printed as hex digits,
        if raw is passed, the data is printed as received from the device.
        """

        if encoding not in ['raw', 'hex']:
            raise ValidationError("Unknown encoding type specified in dump trace",
                                  encoding=encoding, known_encodings=['hex', 'raw'])

        if self._trace_queue is None:
            return ""

        self._accumulate_trace()

        if encoding == 'raw':
            return bytes(self._trace_data)

        return binascii.hexlify(self._trace_data).decode('utf-8')

    def wait_trace(self, size, timeout=None, drop_before=False, progress_callback=None):
        """Wait for a specific amount of tracing data to be received.

        This function is the equivalent of wait_reports for streaming data.
        It allows you to block until a specific amount of tracing data has
        been received.  The optional timeout parameter allows you to stop
        waiting if you never receive enough tracing data after a specific
        amount of time.

        Args:
            size (int): The number of bytes to wait for.
            timeout (float): The maximum number of seconds to wait for
                these bytes to be received.
            drop_before (bool): Truncate all data received until now
                before waiting for size bytes.
            progress_callback (callable): An optional progress callback that
                is called periodically with updates.  It should have the
                signature progress_callback(received_byte_count, total_byte_count)

        Returns:
            bytearray: The raw trace data obtained.
        """

        if drop_before:
            self._trace_data = bytearray()

        if progress_callback is None:
            progress_callback = lambda x, y: None

        if len(self._trace_data) >= size:
            progress_callback(size, size)

            data = self._trace_data[:size]
            self._trace_data = self._trace_data[size:]

            return data

        progress_callback(len(self._trace_data), size)

        start = time.time()
        while len(self._trace_data) < size:
            progress_callback(len(self._trace_data), size)
            self._accumulate_trace()

            time.sleep(0.1)
            now = time.time()

            if timeout is not None and ((now - start) > timeout):
                raise TimeoutExpiredError("Timeout waiting for tracing data", expected_size=size,
                                          received_size=len(self._trace_data), timeout=timeout)

        progress_callback(size, size)

        data = self._trace_data[:size]
        self._trace_data = self._trace_data[size:]

        return data

    def _accumulate_trace(self):
        """Copy tracing data from trace queue into _trace_data"""

        if self._trace_queue is None:
            return

        try:
            while True:
                blob = self._trace_queue.get(block=False)
                self._trace_data += bytearray(blob)
        except Empty:
            pass

    def iter_broadcast_reports(self, blocking=False):
        """Iterate over broadcast reports that have been received.

        This function is designed to allow the creation of dispatch or
        processing systems that process broadcast reports as they come in.

        Args:
            blocking (bool): Whether to stop when there are no more readings or
                block and wait for more.
        """

        if self._broadcast_queue is None:
            return

        try:
            while True:
                yield self._broadcast_queue.get(block=blocking)
        except Empty:
            pass

    def wait_broadcast_reports(self, num_reports, timeout=2.0):
        """Wait until a specific number of broadcast reports have been received.

        Args:
            num_reports (int): The number of reports to wait for
            timeout (float): The maximum number of seconds to wait without
                receiving another report.
        """

        if self._broadcast_queue is None:
            raise ExternalError("You have to enable broadcasting before you can wait for broadcast reports")

        reports = []

        for i in range(0, num_reports):
            try:
                report = self._broadcast_queue.get(timeout=timeout)
                reports.append(report)
            except Empty:
                raise TimeoutExpiredError("Timeout waiting for a report", expected_number=num_reports,
                                          received_number=i, received_reports=reports)

        return reports

    def iter_reports(self, blocking=False):
        """Iterate over reports that have been received.

        If blocking is True, this iterator will never stop.  Otherwise
        it will iterate over all reports currently in the queue (and those
        added during iteration)

        Args:
            blocking (bool): Whether to stop when there are no more readings or
                block and wait for more.
        """
        if self._stream_queue is None:
            return

        try:
            while True:
                yield self._stream_queue.get(block=blocking)
        except Empty:
            pass

    def wait_reports(self, num_reports, timeout=2.0):
        """Wait for a fixed number of reports to be received

        Args:
            num_reports (int): The number of reports to wait for
            timeout (float): The maximum number of seconds to wait without
                receiving another report.
        """

        if self._stream_queue is None:
            raise ExternalError("You have to enable streaming before you can wait for reports")

        reports = []

        for i in range(0, num_reports):
            try:
                report = self._stream_queue.get(timeout=timeout)
                reports.append(report)
            except Empty:
                raise TimeoutExpiredError("Timeout waiting for a report", expected_number=num_reports,
                                          received_number=i, received_reports=reports)

        return reports

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.close()
        return False

    @finalizer
    def close(self):
        """Stop and close this HardwareManager.

        This method will stop all background device activity and prevent any
        further usage of this HardwareManager object.  If RPCs are being
        recorded, this will also save the recording to a file.
        """

        self.stream.close()

    @return_type("list(basic_dict)")
    @param("wait", "float", desc="Time to wait for devices to show up before returning")
    @param("sort", "string", desc="Sort scan results by a key named key")
    @param("limit", "integer", desc="Limit results to the first n devices")
    @param("reverse", "bool", desc="Reverse the sort order")
    def scan(self, wait=None, sort=None, reverse=False, limit=None):
        """Scan for available devices and print a dictionary of information about them.

        If wait is specified as a floating point number in seconds, then the
        default wait times configured inside of the stream or device adapter
        used to find IOTile devices is overridden with the value specified.

        Args:
            wait (float): An optional override time to wait for results to accumulate before returning
            sort (string): An optional key to sort by
            reverse (bool): An optional key that will reverse the sort from ascending to descending
            limit (integer): An optional limit to the number of devices to return
        """

        devices = self.stream.scan(wait=wait)

        for device in devices:
            # Add a Device Slug for user convenience
            if 'uuid' in device:
                device['slug'] = uuid_to_slug(device['uuid'])

        if sort is not None:
            devices.sort(key=lambda x: x[sort], reverse=reverse)

        if limit is not None:
            devices = devices[:limit]

        # FIXME: Use dictionary format in bled112stream to document information returned about devices
        return devices

    def get_proxy(self, short_name, version):
        """Find a proxy type given its short name.

        If no proxy type is found, return None.
        """

        if short_name not in self._name_map:
            return None

        proxy_match = self.find_correct_proxy_version(self._name_map[short_name], version)
        return proxy_match if proxy_match is not None else self._name_map[short_name][0]

    def find_correct_proxy_version(self, proxies, version):
        """Retrieves the ModuleVersion of each proxy and match it with the tile version

        something

        Args:
            proxies (list): A list of proxies of a specific short name
            version (obj): A tuple that specifies the tile's version
        """

        proxy_details = {}
        tile_version = SemanticVersion(version[0], version[1], version[2])
        min_version = SemanticVersion(0, 0, 0)
        best_proxy = None
        self.logger.debug("Short name matched proxies found: {0}".format(proxies))
        for proxy in proxies:
            proxy_details[proxy] = {}
            try:
                # If proxy has ModuleVersion(), get the SemanticVersionRange
                module_version = proxy.ModuleVersion()
                least_version = module_version._disjuncts[0][0][0]
            except AttributeError:
                # If proxy does not have ModuleVersion(), use None
                module_version = None
                least_version = SemanticVersion(0, 0, 0)

            if module_version is None:
                # Regardless if version is compatible, choose a best proxy for now
                if min_version == SemanticVersion(0, 0, 0):
                    best_proxy = proxy
                    self.logger.debug("Found a proxy without ModuleVersion info: {0}".format(proxy))
            elif module_version.check(tile_version):
                # Set best proxy since it matches SVR and update min_version to beat
                if least_version > min_version:
                    min_version = least_version
                    best_proxy = proxy
                    self.logger.debug("Found a compatible proxy: {0}".format(proxy))
                else:
                    self.logger.debug("Passed compatible proxy: {0}".format(proxy))

        self.logger.debug("Best proxy found: {0} with base version {1}".format(best_proxy, min_version))
        # If we don't make it in either conditional, best_proxy will return None
        return best_proxy

    def _create_proxy(self, proxy, address):
        """
        Create a python proxy object to talk to an IOTile module with the given type
        at the given address.
        """

        if proxy not in self._proxies:
            raise UnknownModuleTypeError("unknown proxy module specified", module_type=proxy, known_types=list(self._proxies))

        proxy_class = self._proxies[proxy]
        return proxy_class(self.stream, address)

    def _create_stream(self, force_adapter=None, record=None):
        conn_string = None
        port = self.port

        if port is not None:
            port = port.strip()

        # Check if we're supposed to use a specific device adapter
        if force_adapter is not None:
            return AdapterStream(force_adapter, record=record)

        # Attempt to find a DeviceAdapter that can handle this transport type
        reg = ComponentRegistry()

        for _, adapter_factory in reg.load_extensions('iotile.device_adapter', name_filter=self.transport):
            return AdapterStream(adapter_factory(port), record=record)

        raise HardwareError("Could not find transport object registered to handle passed transport type",
                            transport=self.transport)
