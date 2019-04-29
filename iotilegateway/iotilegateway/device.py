"""A device adapter that aggregates multiple other device adapters.

:class:`AggregatingDeviceAdapter` is compatible with
:class:`AbstractDeviceAdapter` and can be used in the same way.  It's purpose
is to aggregate the views of multiple device adapters together and present
them as a single unified device adapter.

So, connecting to a device will automatically connect through the best device
adapter that can see that device and has an open connection slot.  You can
force a connection to use a specific device adapter by using a specially
formatted connection string if you don't want the automatic behavior.

TODO:
- [ ] Periodically expire devices from visible_devices
- [ ] Add threadsafe mutex around visible_devices
"""

import logging
import copy
from time import monotonic
import functools
from iotile.core.exceptions import ArgumentError, InternalError
from iotile.core.utilities import SharedLoop
from iotile.core.hw.transport.adapter import AbstractDeviceAdapter, BasicNotificationMixin, PerConnectionDataMixin, DeviceAdapter, AsynchronousModernWrapper
from iotile.core.hw.exceptions import DeviceAdapterError


_MISSING = object()

class AggregatingDeviceAdapter(BasicNotificationMixin,
                               PerConnectionDataMixin,
                               AbstractDeviceAdapter):
    """Aggregates multiple device adapters together.

    This class aggregate all of the available devices across each
    DeviceAdapter that is added to it and route connections to the appropriate
    adapter as connections are requested.  An API is provided to make
    connections to devices, monitor events that happen on devices and remember
    what devices have been seen on different adapters.

    It is assumed that devices have unique identifiers so if the same device
    is seen by multiple DeviceAdapters, those different instances are unified
    and the best route to the device is chosen when a user tries to connect to
    it.  For this purpose there is an abstract notion of 'signal_strength'
    that is reported by each DeviceAdapter and used to rank which one has a
    better route to a given device.

    Args:
        loop (BackgroundEventLoop): The background event loop that we should
            use to run our adapters.   Defaults to :class:`SharedLoop`.
    """

    def __init__(self, port=None, adapters=None, loop=SharedLoop):
        BasicNotificationMixin.__init__(self, loop)
        PerConnectionDataMixin.__init__(self)
        AbstractDeviceAdapter.__init__(self)

        self._config = {}
        self._devices = {}
        self._conn_strings = {}
        self.adapters = []
        self.connections = {}
        self._started = False
        self._logger = logging.getLogger(__name__)
        self._next_conn_id = 0

        #TODO: Process port string

        self.set_config('probe_supported', True)
        self.set_config('probe_required', True)

        if adapters is None:
            adapters = []

        for adapter in adapters:
            self.add_adapter(adapter)

    def add_adapter(self, adapter):
        """Add a device adapter to this aggregating adapter."""

        if self._started:
            raise InternalError("New adapters cannot be added after start() is called")

        if isinstance(adapter, DeviceAdapter):
            self._logger.warning("Wrapping legacy device adapter %s in async wrapper", adapter)
            adapter = AsynchronousModernWrapper(adapter, loop=self._loop)

        self.adapters.append(adapter)

        adapter_callback = functools.partial(self.handle_adapter_event,
                                             len(self.adapters) - 1)
        events = ['device_seen', 'broadcast', 'report', 'connection',
                  'disconnection', 'trace', 'progress']

        adapter.register_monitor([None], events, adapter_callback)

    def unique_conn_id(self):
        """Generate a new unique connection id.

        See :meth:`AbstractDeviceAdapter.unique_conn_id`.

        Returns:
            int: A new, unique integer suitable for use as a conn_id.
        """

        next_id = self._next_conn_id
        self._next_conn_id += 1
        return next_id

    def get_config(self, name, default=_MISSING):
        """Get a configuration setting from this DeviceAdapter.

        See :meth:`AbstractDeviceAdapter.get_config`.
        """

        val = self._config.get(name, default)
        if val is _MISSING:
            raise ArgumentError("DeviceAdapter config {} did not exist and no default".format(name))

        return val

    def set_config(self, name, value):
        """Adjust a configuration setting on this DeviceAdapter.

        See :meth:`AbstractDeviceAdapter.set_config`.
        """

        self._config[name] = value

    def can_connect(self):
        """Return whether this device adapter can accept another connection.

        We just generically return that we can always connect to one more
        device.

        See :meth:`AbstractDeviceAdapter.can_connect`.
        """

        return True

    async def start(self):
        """Start all adapters managed by this device adapter.

        If there is an error starting one or more adapters, this method will
        stop any adapters that we successfully started and raise an exception.
        """

        successful = 0

        try:
            for adapter in self.adapters:
                await adapter.start()
                successful += 1

            self._started = True
        except:
            for adapter in self.adapters[:successful]:
                await adapter.stop()

            raise

    async def stop(self):
        """Stop all adapters managed by this device adapter."""

        for adapter in self.adapters:
            await adapter.stop()

    def visible_devices(self):
        """Unify all visible devices across all connected adapters

        Returns:
            dict: A dictionary mapping UUIDs to device information dictionaries
        """

        devs = {}

        for device_id, adapters in self._devices.items():
            dev = None
            max_signal = None
            best_adapter = None

            for adapter_id, devinfo in adapters.items():
                connstring = "adapter/{0}/{1}".format(adapter_id, devinfo['connection_string'])
                if dev is None:
                    dev = copy.deepcopy(devinfo)
                    del dev['connection_string']

                if 'adapters' not in dev:
                    dev['adapters'] = []
                    best_adapter = adapter_id

                dev['adapters'].append((adapter_id, devinfo['signal_strength'], connstring))

                if max_signal is None:
                    max_signal = devinfo['signal_strength']
                elif devinfo['signal_strength'] > max_signal:
                    max_signal = devinfo['signal_strength']
                    best_adapter = adapter_id

            # If device has been seen in no adapters, it will get expired
            # don't return it
            if dev is None:
                continue

            dev['connection_string'] = "device/%x" % dev['uuid']
            dev['adapters'] = sorted(dev['adapters'], key=lambda x: x[1], reverse=True)
            dev['best_adapter'] = best_adapter
            dev['signal_strength'] = max_signal

            devs[device_id] = dev

        return devs

    async def connect(self, conn_id, connection_string):
        """Connect to a device.

        See :meth:`AbstractDeviceAdapter.connect`.
        """

        if connection_string.startswith('device/'):
            adapter_id, local_conn = self._find_best_adapter(connection_string, conn_id)
            translate_conn = True
        elif connection_string.startswith('adapter/'):
            adapter_str, _, local_conn = connection_string[8:].partition('/')
            adapter_id = int(adapter_str)
            translate_conn = False
        else:
            raise DeviceAdapterError(conn_id, 'connect', 'invalid connection string format')

        if self.adapters[adapter_id].can_connect() is False:
            raise DeviceAdapterError(conn_id, 'connect', 'chosen adapter cannot handle another connection')

        # Make sure to set up the connection information before
        # so there are no races with events coming soon after connect.
        self._setup_connection(conn_id, local_conn)
        self._track_property(conn_id, 'adapter', adapter_id)
        self._track_property(conn_id, 'translate', translate_conn)

        try:
            await self.adapters[adapter_id].connect(conn_id, local_conn)
        except:
            self._teardown_connection(conn_id)
            raise

    async def disconnect(self, conn_id):
        """Disconnect from a connected device.

        See :meth:`AbstractDeviceAdapter.disconnect`.
        """

        adapter_id = self._get_property(conn_id, 'adapter')
        await self.adapters[adapter_id].disconnect(conn_id)

        self._teardown_connection(conn_id)

    async def open_interface(self, conn_id, interface):
        """Open an interface on an IOTile device.

        See :meth:`AbstractDeviceAdapter.open_interface`.
        """

        adapter_id = self._get_property(conn_id, 'adapter')
        await self.adapters[adapter_id].open_interface(conn_id, interface)


    async def close_interface(self, conn_id, interface):
        """Close an interface on this IOTile device.

        See :meth:`AbstractDeviceAdapter.close_interface`.
        """

        adapter_id = self._get_property(conn_id, 'adapter')
        await self.adapters[adapter_id].close_interface(conn_id, interface)

    async def probe(self):
        """Probe for devices.

        This method will probe all adapters that can probe and will send a
        notification for all devices that we have seen from all adapters.

        See :meth:`AbstractDeviceAdapter.probe`.
        """

        for adapter in self.adapters:
            if adapter.get_config('probe_supported', False):
                await adapter.probe()

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Send an RPC to a device.

        See :meth:`AbstractDeviceAdapter.send_rpc`.
        """

        adapter_id = self._get_property(conn_id, 'adapter')
        return await self.adapters[adapter_id].send_rpc(conn_id, address, rpc_id, payload, timeout)

    async def debug(self, conn_id, name, cmd_args):
        """Send a debug command to a device.

        See :meth:`AbstractDeviceAdapter.debug`.
        """

        adapter_id = self._get_property(conn_id, 'adapter')
        return await self.adapters[adapter_id].debug(conn_id, name, cmd_args)

    async def send_script(self, conn_id, data):
        """Send a script to a device.

        See :meth:`AbstractDeviceAdapter.send_script`.
        """

        adapter_id = self._get_property(conn_id, 'adapter')
        return await self.adapters[adapter_id].send_script(conn_id, data)

    async def handle_adapter_event(self, adapter_id, conn_string, conn_id, name, event):
        """Handle an event received from an adapter."""

        if name == 'device_seen':
            self._track_device_seen(adapter_id, conn_string, event)
            event = self._translate_device_seen(adapter_id, conn_string, event)

            conn_string = self._translate_conn_string(adapter_id, conn_string)
        elif conn_id is not None and self._get_property(conn_id, 'translate'):
            conn_string = self._translate_conn_string(adapter_id, conn_string)
        else:
            conn_string = "adapter/%d/%s" % (adapter_id, conn_string)

        await self.notify_event(conn_string, name, event)

    def _track_device_seen(self, adapter_id, conn_string, event):
        universal_conn = "device/%x" % event.get('uuid')
        local_conn = "adapter/%d/%s" % (adapter_id, conn_string)

        if universal_conn not in self._devices:
            self._devices[universal_conn] = {}

        event['expires'] = monotonic() + event.get('validity_period')
        self._devices[universal_conn][adapter_id] = event
        self._conn_strings[local_conn] = universal_conn

    def _translate_device_seen(self, adapter_id, conn_string, event):
        universal_conn = self._translate_conn_string(adapter_id, conn_string)

        translated_event = dict(uuid=event.get('uuid'), connection_string=universal_conn)
        return translated_event

    def _translate_conn_string(self, adapter_id, conn_string):
        local_conn = "adapter/%d/%s" % (adapter_id, conn_string)
        return self._conn_strings.get(local_conn)

    def _find_best_adapter(self, universal_conn, conn_id):
        if universal_conn not in self._devices:
            raise DeviceAdapterError(conn_id, 'find_best_adapter', 'device not seen on any adapters')

        for adapter_id, dev in self._devices[universal_conn].items():
            if self.adapters[adapter_id].can_connect():
                return adapter_id, dev.get('connection_string')

        raise DeviceAdapterError(conn_id, 'find_best_adapter', 'no adapter has space for connection')

    def _device_expiry_callback(self):
        """Periodic callback to remove expired devices from visible_devices."""

        expired = 0
        for adapters in self._devices.values():
            to_remove = []
            now = monotonic()

            for adapter_id, dev in adapters.items():
                if 'expires' not in dev:
                    continue

                if now > dev['expires']:
                    to_remove.append(adapter_id)
                    local_conn = "adapter/%d/%s" % (adapter_id, dev['connection_string'])

                    if local_conn in self._conn_strings:
                        del self._conn_strings[local_conn]

            for entry in to_remove:
                del adapters[entry]
                expired += 1

        if expired > 0:
            self._logger.info('Expired %d devices', expired)
