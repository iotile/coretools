"""DeviceAdapter that connects to virtual devices that are run inside the same process.

This adapter is very useful for integration testing other systems that depends
on device interaction since you can create whatever kind of situation you want
using a virtual device and to anyone outside of HardwareManager, there is no
way to tell they are not talking to a physical iotile device.

This adapter also forms the basis for transparent proxying of device access.
Using a combination of a DeviceServer class attached to a VirtaulDevice, you
can project any virtual device out into the world as a connectable iotile
device over any protocol supported by an installed device adapter.  This could
let you, for example, serve a virtual device from your computer over bluetooth
low energy that lets users control your computer from their mobile phone.
"""

import json
import logging
import inspect
from iotile.core.exceptions import ArgumentError
from iotile.core.dev import ComponentRegistry
from iotile.core.hw.reports import BroadcastReport
from iotile.core.hw.exceptions import DevicePushError
from iotile.core.utilities import SharedLoop
from ..exceptions import DeviceAdapterError, VALID_RPC_EXCEPTIONS
from ..virtual import BaseVirtualDevice, AbstractAsyncDeviceChannel
from .adapter import StandardDeviceAdapter


class VirtualAdapterAsyncChannel(AbstractAsyncDeviceChannel):
    """A channel for tracing and streaming data asynchronously from virtual devices"""

    def __init__(self, adapter, iotile_id):
        self.adapter = adapter
        self.iotile_id = iotile_id
        self.conn_string = str(iotile_id)

    async def stream(self, report):
        """Queue data for streaming

        Args:
            report (IOTileReport): A report object to stream to a client
        """

        conn_id = self._find_connection(self.conn_string)

        if isinstance(report, BroadcastReport):
            await self.adapter.notify_event(self.conn_string, 'broadcast', report)
        elif conn_id is not None:
            await self.adapter.notify_event(self.conn_string, 'report', report)
        else:
            raise DevicePushError("Cannot push report because no client is connected")

    async def trace(self, data):
        """Queue data for tracing

        Args:
            data (bytes): Unstructured data to trace to any
                connected client.
        """

        conn_id = self._find_connection(self.conn_string)

        if conn_id is not None:
            await self.adapter.notify_event(self.conn_string, 'trace', data)
        else:
            raise DevicePushError("Cannot push tracing data because no client is connected")

    async def disconnect(self):
        """Forcibly disconnect a connected client."""

        raise DevicePushError("Disconnection is not yet supported")

    def _find_connection(self, conn_string):
        """Find the connection corresponding to an iotile_id."""

        return self.adapter._get_conn_id(conn_string)


class VirtualDeviceAdapter(StandardDeviceAdapter):
    """Device adapter that gives access to one or more virtual devices

    The adapter is created and serves access to the virtual_devices that are
    found by name in the entry_point group iotile.virtual_device.

    There are two ways to passing configuration dictionaries down into a
    VirtualDevice attached to this VirtualDeviceAdapter.  Both are performed
    by encoding the port string with {{device_name}}@{{config_info}}.  You
    can either pass a path to a json file in {{config_info}} which is loaded
    as a dictionary or you can prepend a '#' to the front of config_info and
    pass a base64 encoded json string that is decoded into a dict.  Both are
    identically passed to the underlying __init__ function of the VirtualDevice

    If you choose to use a json file, the format must be::

        {
            "device":
            {
                ARGS GO HERE
            }
        }

    The required device key is to allow for this file to host information about
    multiple other kinds of iotile entities without collisions.

    If you are programmatically specifying the dictionary then it should just
    be a normal json with no parent "device" key such as:

        {
            ARGS GO HERE
        }

    Args:
        port (string): A port description that should be in the form of
            device_name1@<optional_config_json1;device_name2@optional_config_json2
        devices (list of BaseVirtualDevice): Optional list of precreated virtual
            devices that you would like to add to this virtual adapter.  It can sometimes
            be easier to pass precreated devices rather than needing to specify how
            they should be created.
    """

    # Make devices expire after a long time only
    ExpirationTime = 600000

    def __init__(self, port=None, devices=None, loop=SharedLoop):
        super(VirtualDeviceAdapter, self).__init__(name=__name__, loop=loop)

        loaded_devs = {}

        if devices is None:
            devices = []

        if port is not None:
            devs = port.split(';')

            for dev in devs:
                name, _sep, config = dev.partition('@')

                if len(config) == 0:
                    config = None

                loaded_dev = self._load_device(name, config)

                if not self._validate_device(loaded_dev):
                    raise ArgumentError("Device type cannot be loaded on this adapter", name=name)

                loaded_devs[loaded_dev.iotile_id] = loaded_dev

        # Allow explicitly passing created VirtualDevice subclasses
        for dev in devices:
            if not self._validate_device(dev):
                raise ArgumentError("Device type cannot be loaded on this adapter", name=name)

            loaded_devs[dev.iotile_id] = dev

        self.devices = loaded_devs
        self.scan_interval = self.get_config('scan_interval', 1.0)
        self.last_scan = None
        self._logger = logging.getLogger(__name__)

        self.set_config('probe_required', True)
        self.set_config('probe_supported', True)

    async def start(self):
        for dev in self.devices.values():
            await self._loop.run_in_executor(dev.start, VirtualAdapterAsyncChannel(self, dev.iotile_id))

    # pylint:disable=unused-argument;The name needs to remain without an _ for subclasses to override
    @classmethod
    def _validate_device(cls, device):
        """Hook for subclases to ensure that only specific kinds of devices are loaded.

        The default implementation just returns True, allowing all virtual devices.

        Returns:
            bool: Whether the virtual device is allowed to load.
        """

        return True

    def _load_device(self, name, config):
        """Load a device either from a script or from an installed module"""

        if config is None:
            config_dict = {}
        elif isinstance(config, dict):
            config_dict = config
        elif config[0] == '#':
            # Allow passing base64 encoded json directly in the port string to ease testing.
            import base64
            config_str = str(base64.b64decode(config[1:]), 'utf-8')
            config_dict = json.loads(config_str)
        else:
            try:
                with open(config, "r") as conf:
                    data = json.load(conf)
            except IOError as exc:
                raise ArgumentError("Could not open config file", error=str(exc), path=config)

            if 'device' not in data:
                raise ArgumentError("Invalid configuration file passed to VirtualDeviceAdapter",
                                    device_name=name, config_path=config, missing_key='device')

            config_dict = data['device']

        reg = ComponentRegistry()

        if name.endswith('.py'):
            _name, device_factory = reg.load_extension(name, class_filter=BaseVirtualDevice, unique=True)
            return _instantiate_virtual_device(device_factory, config_dict, self._loop)

        seen_names = []
        for device_name, device_factory in reg.load_extensions('iotile.virtual_device',
                                                               class_filter=BaseVirtualDevice,
                                                               product_name="virtual_device"):
            if device_name == name:
                return _instantiate_virtual_device(device_factory, config_dict, self._loop)

            seen_names.append(device_name)

        raise ArgumentError("Could not find virtual_device by name", name=name, known_names=seen_names)

    def can_connect(self):
        """Return whether this device adapter can accept another connection."""

        return True

    async def connect(self, conn_id, connection_string):
        """Asynchronously connect to a device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.
            callback (callable): A function that will be called when the connection attempt finishes as
                callback(conection_id, adapter_id, success: bool, failure_reason: string or None)
        """

        id_number = int(connection_string)
        if id_number not in self.devices:
            raise DeviceAdapterError(conn_id, 'connect', 'device not found')

        if self._get_conn_id(connection_string) is not None:
            raise DeviceAdapterError(conn_id, 'connect', 'device already connected')

        dev = self.devices[id_number]

        if dev.connected:
            raise DeviceAdapterError(conn_id, 'connect', 'device already connected')

        await dev.connect()

        self._setup_connection(conn_id, connection_string)
        self._track_property(conn_id, 'device', dev)

    async def disconnect(self, conn_id):
        """Asynchronously disconnect from a connected device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        self._ensure_connection(conn_id, True)

        dev = self._get_property(conn_id, 'device')
        await dev.disconnect()

        self._teardown_connection(conn_id)

    async def open_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, True)

        dev = self._get_property(conn_id, 'device')
        conn_string = self._get_property(conn_id, 'connection_string')

        result = await dev.open_interface(interface)

        if interface == 'streaming' and result is not None:
            for report in result:
                await self.notify_event(conn_string, 'report', report)
        elif interface == 'tracing' and result is not None:
            for trace in result:
                await self.notify_event(conn_string, 'trace', trace)
        elif result is not None:
            self._logger.warning("Discarding non-None result from open_interface call: %s", result)

    async def close_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, True)

        dev = self._get_property(conn_id, 'device')
        await dev.close_interface(interface)

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Asynchronously send an RPC to this IOTile device.

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            address (int): the address of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
        """

        self._ensure_connection(conn_id, True)
        dev = self._get_property(conn_id, 'device')

        try:
            return await dev.async_rpc(address, rpc_id, bytes(payload))
        except VALID_RPC_EXCEPTIONS:
            raise
        except Exception:
            self._logger.exception("Exception inside rpc %d:0x%04X, payload=%s",
                                   address, rpc_id, payload)
            raise

    async def send_script(self, conn_id, data):
        """Asynchronously send a script to this IOTile device.

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            data (bytes or bytearray): the script to send to the device
        """

        self._ensure_connection(conn_id, True)
        dev = self._get_property(conn_id, 'device')
        conn_string = self._get_property(conn_id, 'connection_string')

        # Simulate some progress callbacks (0, 50%, 100%)
        await self.notify_progress(conn_string, 'script', 0, len(data))
        await self.notify_progress(conn_string, 'script', len(data) // 2, len(data))
        await self.notify_progress(conn_string, 'script', len(data), len(data))

        dev.script = data

    async def debug(self, conn_id, name, cmd_args):
        """Send a debug command to a device.

        This method responds to a single command 'inspect_property' that takes
        the name of a propery on the device and returns its value.  The
        ``cmd_args`` dict should have a single key: 'properties' that is a
        list of strings with the property names that should be returned.

        Those properties are all queried and their result returned.

        The result is a dict that maps property name to value.  There is a
        progress event generated for every property whose purpose is primarily
        to allow for testing the progress system of a device server.

        See :meth:`AbstractDeviceAdapter.debug`.
        """

        self._ensure_connection(conn_id, True)
        dev = self._get_property(conn_id, 'device')
        conn_string = self._get_property(conn_id, 'connection_string')

        if name != 'inspect_property':
            raise DeviceAdapterError(conn_id, 'debug', 'operation {} not supported'.format(name))

        properties = cmd_args.get('properties', [])

        result = {}

        for i, prop in enumerate(properties):
            if not hasattr(dev, prop):
                raise DeviceAdapterError(conn_id, 'debug', 'property {} did not exist'.format(prop))

            value = getattr(dev, prop)
            result[prop] = value

            await self.notify_progress(conn_string, 'debug', i + 1, len(properties))

        return result

    async def _send_scan_event(self, device):
        """Send a scan event from a device."""

        conn_string = str(device.iotile_id)
        info = {
            'connection_string': conn_string,
            'uuid': device.iotile_id,
            'signal_strength': 100,
            'validity_period': self.ExpirationTime
        }

        await self.notify_event(conn_string, 'device_seen', info)

    async def stop(self):
        for dev in self.devices.values():
            await self._loop.run_in_executor(dev.stop)

    async def probe(self):
        """Send advertisements for all connected virtual devices."""

        for dev in self.devices.values():
            await self._send_scan_event(dev)


def _instantiate_virtual_device(factory, config, loop):
    """Safely instantiate a virtualdevice passing a BackgroundEventLoop if necessary."""

    kwargs = dict()

    sig = inspect.signature(factory)
    if 'loop' in sig.parameters:
        kwargs['loop'] = loop

    return factory(config, **kwargs)
