# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.
import time
import inspect
import os.path
import imp
import binascii
import sys
import logging
from queue import Empty
import pkg_resources

from iotile.core.dev.semver import SemanticVersion
from iotile.core.hw.transport import *
from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *
from iotile.core.utilities.typedargs.annotate import param, return_type, finalizer, docannotate
from typedargs import *
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.hw.transport.adapterstream import AdapterCMDStream
from iotile.core.dev.config import ConfigManager
from iotile.core.hw.debug import DebugManager

from .proxy import TileBusProxyObject
from .app import IOTileApp

@context("HardwareManager")
class HardwareManager(object):
    """
    A module for managing and interacting with IOTile Hardware

    This context provides tools to configure, control, debug and program
    any IOTile module.  Specific functionality can be implemented in dynamically
    loaded proxy objects that are designed to provide access to each IOTile.

    To create a HardwareManager, you need to pass a port string that describes the
    method to be used to connect to the IOTile device. The method should specify the
    name of the connection method optionally followed by a colon and any extra information
    possibly needed to connect using that method.
    """

    # Allow overriding proxies for development by adding them to this shared proxy map
    DevelopmentProxies = {}
    DevelopmentApps = {}
    DevelopmentAppNames = {}

    logger = logging.getLogger(__name__)

    @param("port", "string", desc="transport method to use in the format transport[:port[,connection_string]]")
    @param("record", "path", desc="Optional file to record all RPC calls and responses made on this HardwareManager")
    def __init__(self, port=None, record=None):
        if port is None:
            try:
                conf = ConfigManager()
                port = conf.get('core:default-port')
            except ArgumentError:
                raise ArgumentError("No port given and no core:default-port config variable set", suggestion="Specify the port to use to connect to the IOTile devices")

        transport, _, arg = port.partition(':')

        self.transport = transport
        self.port = None
        if arg != "":
            self.port = arg

        self.record = record

        self.stream = self._create_stream()

        self._stream_queue = None
        self._trace_queue = None
        self._trace_data = bytearray()

        self._proxies = {'TileBusProxyObject': TileBusProxyObject}
        self._name_map = {TileBusProxyObject.ModuleName(): [TileBusProxyObject]}

        self._known_apps = {}
        self._named_apps = {}

        self._setup_proxies()
        self._setup_apps()

    @classmethod
    def RegisterDevelopmentProxy(cls, proxy_obj):  # pylint: disable=C0103; class methods are capitalized when expected to be invoked on types
        """Register a proxy object that should be available for local development.

        Often during development, you need to create a virtual iotile device with
        its own proxy object.  It's easy to point CoreTools at the virtual device
        in order to test it, but there did not use to be a good way to load in
        its proxy object.  This method allows the user to inject a development
        proxy module to use with the virtual device.

        Args:
            proxy_obj (TileBusProxyObject): The proxy module class that should be
                registered.
        """

        name = proxy_obj.ModuleName()

        if name not in HardwareManager.DevelopmentProxies:
            HardwareManager.DevelopmentProxies[name] = []

        HardwareManager.DevelopmentProxies[name].append(proxy_obj)

    @classmethod
    def ClearDevelopmentApps(cls):
        """Clear all development apps previously registered."""

        cls.DevelopmentAppNames = {}
        cls.DevelopmentApps = {}

    @classmethod
    def RegisterDevelopmentApp(cls, app):  # pylint: disable=C0103; class methods are capitalized when expected to be invoked on types
        """Register an IOTileApp object that should be available for local development.

        Often during development, you need to create a virtual iotile device with
        its own app object.  It's easy to point CoreTools at the virtual device
        in order to test it, but there did not use to be a good way to load in
        its app object.  This method allows the user to inject a development
        app module to use with the virtual device.

        Args:
            app (TileBusApp): The app module class that should be
                registered.
        """

        matches = app.MatchInfo()

        for (app_tag, ver_range, quality) in matches:
            if app_tag not in HardwareManager.DevelopmentApps:
                HardwareManager.DevelopmentApps[app_tag] = []

            HardwareManager.DevelopmentApps[app_tag].append((ver_range, quality, app))

        HardwareManager.DevelopmentAppNames[app.AppName()] = app

    def _setup_proxies(self):
        """Load in proxy module objects for all of the registered components on this system."""

        # Find all of the registered IOTile components and see if we need to add any proxies for them
        reg = ComponentRegistry()
        modules = reg.list_components()

        proxies = reduce(lambda x, y: x+y, [reg.find_component(x).proxy_modules() for x in modules], [])
        proxy_classes = []
        for prox in proxies:
            proxy_classes += self._load_module_classes(prox, TileBusProxyObject)

        # Find all installed proxy objects through registered entry points
        for entry in pkg_resources.iter_entry_points('iotile.proxy'):
            mod = entry.load()
            proxy_classes += [x for x in mod.__dict__.itervalues() if inspect.isclass(x) and issubclass(x, TileBusProxyObject) and x != TileBusProxyObject]

        for obj in proxy_classes:
            if obj.__name__ in self._proxies:
                continue #Don't readd proxies that we already know about

            self._proxies[obj.__name__] = obj

            #Check if this object matches a specific shortened name so that we can
            #automatically match a hw module to a proxy without user intervention
            try:
                short_name = obj.ModuleName()
                if short_name in self._name_map:
                    self._name_map[short_name].append(obj)
                else:
                    self._name_map[short_name] = [obj]
            except Exception:  #pylint: disable=broad-except;We don't want this to die if someone loads a misbehaving plugin
                self.logger.exception("Error importing misbehaving proxy module, skipping.")

    def _setup_apps(self):
        """Load in all iotile app objects for all registered or installed components on this system."""

        reg = ComponentRegistry()
        modules = reg.list_components()

        apps = reduce(lambda x, y: x+y, [reg.find_component(x).app_modules() for x in modules], [])
        app_classes = []
        for app in apps:
            app_classes += self._load_module_classes(app, IOTileApp)

        # Find all installed proxy objects through registered entry points
        for entry in pkg_resources.iter_entry_points('iotile.app'):
            mod = entry.load()
            app_classes += [x for x in mod.__dict__.itervalues() if inspect.isclass(x) and issubclass(x, IOTileApp) and x != IOTileApp]

        for app in app_classes:
            try:
                matches = app.MatchInfo()
                name = app.AppName()
                for tag, ver_range, quality in matches:
                    if tag not in self._known_apps:
                        self._known_apps[tag] = []

                    self._known_apps[tag].append((ver_range, quality, app))

                if name in self._named_apps:
                    self.logger.warn("Added an app module with an existing name, overriding previous app, name=%s", name)

                self._named_apps[name] = app
            except Exception:  #pylint: disable=broad-except;We don't want this to die if someone loads a misbehaving plugin
                self.logger.exception("Error importing misbehaving app module, skipping.")

    @param("address", "integer", "positive", desc="numerical address of module to get")
    @param("basic", "bool", desc="return a basic global proxy rather than a specialized one")
    def get(self, address, basic=False):
        """Create a proxy object for a tile by address.

        The correct proxy object is determined by asking the tile for its
        status information and looking up the appropriate proxy in our list of
        installed proxy objects.  If you want to send raw RPCs, you can get a
        basic TileBusProxyObject by passing basic=True.
        """

        tile = self._create_proxy('TileBusProxyObject', address)

        if basic:
            return tile

        name = tile.tile_name()
        version = tile.tile_version()

        # Now create the appropriate proxy object based on the name and version of the tile
        tile_type = self.get_proxy(name)
        if tile_type is None:
            raise HardwareError("Could not find proxy object for tile", name="'{}'".format(name), known_names=self._name_map.keys())

        tile = tile_type(self.stream, address)
        tile._hwmanager = self

        return tile

    @docannotate
    def app(self, name=None, path=None):
        """Find the best IOTileApp for the device we are connected to.

        Apps are matched by looking at the app tag and version information
        specified by the connected device.  If no installed app matches, an
        exception will be thrown.  You can also force the matching of a
        specific app by using the name parameter.

        Args:
            name (str): Optional name of the app that you wish to load.
            path (str): Optional path to a python file containing the
                app that you wish to load.

        Returns:
            IOTileApp show-as context: The IOTileApp class that was loaded
                for this device.
        """

        if name is not None and path is not None:
            raise ArgumentError("You cannot specify both an app name and an app path", name=name, path=path)

        # We perform all app matching by asking the device's controller for its app and os info
        tile = self._create_proxy('TileBusProxyObject', 8)
        device_id, os_info, app_info = tile.rpc(0x10, 0x08, result_format="L8xLL")

        os_tag = os_info  & ((1 << 20) - 1)
        os_version_str = '%d.%d.%d'  % ((os_info >> 26) & ((1 << 6) - 1), (os_info >> 20) & ((1 << 6) - 1), 0)

        app_tag = app_info & ((1 << 20) - 1)
        app_version_str = '%d.%d.%d'  % ((app_info >> 26) &  ((1 << 6) - 1), (app_info>>20) & ((1 << 6) - 1), 0)

        os_version = SemanticVersion.FromString(os_version_str)
        app_version = SemanticVersion.FromString(app_version_str)

        app_class = None

        # If name includes a .py, assume that it points to python file and try to load that.
        if name is None and path is not None:
            loaded_classes = self._load_module_classes(path, IOTileApp)
            if len(loaded_classes) > 1:
                raise ArgumentError("app called with a python file that contained more than one IOTileApp class", classes=loaded_classes)
            elif len(loaded_classes) == 0:
                raise ArgumentError("app called with a python file that did not contain any IOTileApp subclasses")

            app_class = loaded_classes[0]
        elif name is not None:
            if name in self.DevelopmentAppNames:
                app_class = self.DevelopmentAppNames[name]
            else:
                app_class = self._named_apps.get(name)
        else:
            best_match = None
            matching_tags = self._known_apps.get(app_tag, [])
            dev_tags = self.DevelopmentApps.get(app_tag, [])

            for (ver_range, quality, app) in matching_tags + dev_tags:
                if ver_range.check(app_version):
                    if best_match is None:
                        best_match = (quality, app)
                    elif quality > best_match[0]:
                        best_match = (quality, app)

            if best_match is not None:
                app_class = best_match[1]

        if app_class is None:
            raise HardwareError("Could not find matching application for device", app_tag=app_tag, explicit_app=name, installed_apps=[x for x in self._named_apps])

        app = app_class(self, (app_tag, app_version), (os_tag, os_version), device_id)
        return app

    @annotated
    def controller(self):
        """
        Find an attached IOTile controller and attempt to connect to it.
        """

        con = self.get(8)
        con._hwmanager = self

        return con

    @param("device_uuid", "integer", desc="UUID of the device we would like to connect to")
    @param("wait", "float", desc="Time to wait for devices to show up before connecting")
    def connect(self, device_uuid, wait=None):
        """Attempt to connect to a device by its UUID
        """

        self.stream.connect(device_uuid, wait=wait)

    @param("connection_string", "string", desc="opaque connection string indicating which device")
    def connect_direct(self, connection_string):
        """Attempt to connect to a device using a connection string
        """

        self.stream.connect_direct(connection_string)

    @annotated
    def disconnect(self):
        """Attempt to disconnect from a device
        """

        self._trace_queue = None
        self._stream_queue = None

        self.stream.disconnect()

    @annotated
    def debug(self):
        """Prepare the device for debugging if supported.

        Some transport mechanisms support a low level debug channel
        that permits recovery and test operations such as erasing
        and forcibly reprogramming a device or dumping memory.

        No debug operations are supported, this function will raise
        an exception.
        """

        self.stream.enable_debug()
        return DebugManager(self.stream)

    @return_type("bool")
    def heartbeat(self):
        """
        Check whether the underlying command stream is functional
        """

        return self.stream.heartbeat()

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

        if self._stream_queue is not None:
            return

        self._stream_queue = self.stream.enable_streaming()

    @annotated
    def enable_tracing(self):
        """Enable tracing of realtime debug information over this interface
        """

        if self._trace_queue is not None:
            return

        self._trace_queue = self.stream.enable_tracing()

    @return_type("integer")
    def count_reports(self):
        if self._stream_queue is None:
            return 0

        return self._stream_queue.qsize()

    @return_type("string")
    @param("encoding", "string", desc="The encoding to use to dump the trace, either 'hex' or 'raw'")
    def dump_trace(self, encoding):
        """Dump all received tracing data currently received from the device to stdout

        The data is encoded per the encoding parmeter which must be either
        the string 'hex' or 'raw'.  If hex is passed, the data is printed as hex digits,
        if raw is passed, the data is printed as received from the device.
        """

        if encoding not in ['raw', 'hex']:
            raise ValidationError("Unknown encoding type specified in dump trace", encoding=encoding, known_encodings=['hex', 'raw'])

        if self._trace_queue is None:
            return ""

        self._accumulate_trace()

        if encoding == 'raw':
            return str(self._trace_data)

        return binascii.hexlify(self._trace_data)

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
                raise TimeoutExpiredError("Timeout waiting for tracing data", expected_size=size, received_size=len(self._trace_data), timeout=timeout)

        progress_callback(size, size)

        data = self._trace_data[:size]
        self._trace_data = self._trace_data[size:]

        return data

    def _accumulate_trace(self):
        """Copy tracing data from trace queue into _trace_data
        """

        if self._trace_queue is None:
            return

        try:
            while True:
                blob = self._trace_queue.get(block=False)
                self._trace_data += bytearray(blob)
        except Empty:
            pass

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

        for i in xrange(0, num_reports):
            try:
                report = self._stream_queue.get(timeout=timeout)
                reports.append(report)
            except Empty:
                raise TimeoutExpiredError("Timeout waiting for a report", expected_number=num_reports, received_number=i, received_reports=reports)

        return reports

    @annotated
    def reset(self):
        """
        Attempt to reset the underlying stream back to a known state
        """

        self.stream.reset()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.close()
        return False

    @finalizer
    def close(self):
        self.stream.close()

    @classmethod
    def _load_module_classes(cls, path, base_class):
        """Load a python module and return all classes that inherit from a given base."""

        folder, basename = os.path.split(path)
        basename, ext = os.path.splitext(basename)
        if ext != '.py' and ext != '.pyc' and ext != "":
            raise ArgumentError("Attempted to load module is not a python package or module (.py or .pyc)", path=path)

        try:
            fileobj, pathname, description = imp.find_module(basename, [folder])

            #Don't load modules twice
            if basename in sys.modules:
                mod = sys.modules[basename]
            else:
                mod = imp.load_module(basename, fileobj, pathname, description)
        except ImportError as exc:
            raise ArgumentError("could not import module in order to load external proxy modules", module_path=path, parent_directory=folder, module_name=basename, error=str(exc))

        # Find all classes in this module that inherit from the given base class
        return [x for x in mod.__dict__.itervalues() if inspect.isclass(x) and issubclass(x, base_class) and x != base_class]

    @return_type("list(basic_dict)")
    @param("wait", "float", desc="Time to wait for devices to show up before returning")
    @param("sort", "string", desc="Sort scan results by a key named key")
    @param("limit", "integer", desc="Limit results to the first n devices")
    @param("reverse", "bool", desc="Reverse the sort order")
    def scan(self, wait=None, sort=None, reverse=False, limit=None):
        """Scan for available devices and print a dictionary of information about them.

        If wait is specified as a floating point number in seconds, then the default wait times
        configured inside of the stream or device adapter used to find IOTile devices is overriden
        with the value specified.

        Args:
            wait (float): An optional override time to wait for results to accumulate before returning
        """

        devices = self.stream.scan(wait=wait)

        if sort is not None:
            devices.sort(key=lambda x: x[sort], reverse=reverse)

        if limit is not None:
            devices = devices[:limit]

        #FIXME: Use dictionary format in bled112stream to document information returned about devices
        return devices

    def get_proxy(self, short_name):
        """
        Find a proxy type given its short name.

        If no proxy type is found, return None.
        """

        if short_name in HardwareManager.DevelopmentProxies:
            return HardwareManager.DevelopmentProxies[short_name][0]

        if short_name not in self._name_map:
            return None

        return self._name_map[short_name][0]

    def _create_proxy(self, proxy, address):
        """
        Create a python proxy object to talk to an IOTile module with the given type
        at the given address.
        """

        if proxy not in self._proxies:
            raise UnknownModuleTypeError("unknown proxy module specified", module_type=proxy, known_types=self._proxies.keys())

        proxy_class = self._proxies[proxy]
        return proxy_class(self.stream, address)

    def _create_stream(self):
        conn_string = None
        port = self.port
        if port is not None and "," in port:
            port, conn_string = port.split(',')

        if port is not None:
            port = port.strip()
        if conn_string is not None:
            conn_string = conn_string.strip()

        #First check if this is the special none stream that creates a transport channel nowhere
        if self.transport == 'none':
            return CMDStream(port, conn_string, record=self.record)

        #Next attempt to find a CMDStream that is registered for this transport type
        for stream_entry in pkg_resources.iter_entry_points('iotile.cmdstream'):
            if stream_entry.name != self.transport:
                continue

            stream_factory = stream_entry.load()
            return stream_factory(port, conn_string, record=self.record)

        #Otherwise attempt to find a DeviceAdapter that we can turn into a CMDStream
        for adapter_entry in pkg_resources.iter_entry_points('iotile.device_adapter'):
            if adapter_entry.name != self.transport:
                continue

            adapter_factory = adapter_entry.load()
            return AdapterCMDStream(adapter_factory(port), port, conn_string, record=self.record)

        raise HardwareError("Could not find transport object registered to handle passed transport type", transport=self.transport)
