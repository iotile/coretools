import json
import logging
from iotile.core.exceptions import ArgumentError
from iotile.core.dev import ComponentRegistry
from iotile.core.hw.reports import BroadcastReport
from .adapter import StandardDeviceAdapter
from ..exceptions import DeviceAdapterError
from ..virtual import (RPCInvalidIDError, TileNotFoundError, RPCNotFoundError,
                       VirtualIOTileDevice, RPCErrorCode)


class VirtualAdapterAsyncChannel:
    """A channel for tracing and streaming data asynchronously from virtual devices"""

    def __init__(self, adapter, iotile_id):
        self.adapter = adapter
        self.iotile_id = iotile_id
        self.conn_string = str(iotile_id)

    def stream(self, report, callback=None):
        """Queue data for streaming

        Args:
            report (IOTileReport): A report object to stream to a client
            callback (callable): An optional callback that will be called with
                a bool value of True when this report actually gets streamed.
                If the client disconnects and the report is dropped instead,
                callback will be called with False
        """

        conn_id = self._find_connection(self.conn_string)

        if isinstance(report, BroadcastReport):
            self.adapter.fire_event(self.conn_string, 'broadcast', report)
        elif conn_id is not None:
            self.adapter.fire_event(self.conn_string, 'report', report)

        if callback is not None:
            callback(isinstance(report, BroadcastReport) or (conn_id is not None))

    def trace(self, data, callback=None):
        """Queue data for tracing

        Args:
            data (bytearray, string): Unstructured data to trace to any
                connected client.
            callback (callable): An optional callback that will be called with
                a bool value of True when this data actually gets traced.
                If the client disconnects and the data is dropped instead,
                callback will be called with False.
        """

        conn_id = self._find_connection(self.conn_string)

        if conn_id is not None:
            self.adapter.fire_event(self.conn_string, 'trace', data)

        if callback is not None:
            callback(conn_id is not None)

    def _find_connection(self, conn_string):
        """Find the connection corresponding to an iotile_id
        """

        return self.adapter._get_conn_id(conn_string)


class AsyncVirtualDeviceAdapter(StandardDeviceAdapter):
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
        devices (list of VirtualIOTileDevice): Optional list of precreated virtual
            devices that you would like to add to this virtual adapter.  It can sometimes
            be easier to pass precreated devices rather than needing to specify how
            they should be created.
    """

    # Make devices expire after a long time only
    ExpirationTime = 600000

    def __init__(self, port=None, devices=None):
        super(AsyncVirtualDeviceAdapter, self).__init__(name=__name__)

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
            dev.start(VirtualAdapterAsyncChannel(self, dev.iotile_id))

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
            _name, device_factory = reg.load_extension(name, class_filter=VirtualIOTileDevice, unique=True)
            return device_factory(config_dict)

        seen_names = []
        for device_name, device_factory in reg.load_extensions('iotile.virtual_device',
                                                               class_filter=VirtualIOTileDevice,
                                                               product_name="virtual_device"):
            if device_name == name:
                return device_factory(config_dict)

            seen_names.append(device_name)

        raise ArgumentError("Could not find virtual_device by name", name=name, known_names=seen_names)

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
        dev.connected = True

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
        dev.connected = False

        self._teardown_connection(conn_id)

    async def open_interface(self, conn_id, interface, connection_string=None):
        self._ensure_connection(conn_id, True)

        dev = self._get_property(conn_id, 'device')
        conn_string = self._get_property(conn_id, 'connection_string')

        result = dev.open_interface(interface)

        if interface == 'streaming' and result is not None:
            for report in result:
                await self.notify_event(conn_string, 'report', report)
        elif interface == 'tracing' and result is not None:
            for trace in result:
                await self.notify_event(conn_string, 'trace', trace)

    async def close_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, True)

        dev = self._get_property(conn_id, 'device')
        dev.close_interface(interface)

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Asynchronously send an RPC to this IOTile device

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
            return dev.call_rpc(address, rpc_id, bytes(payload))
        except (RPCInvalidIDError, RPCNotFoundError, TileNotFoundError, RPCErrorCode):
            raise
        except Exception:
            self._logger.exception("Exception inside rpc %d:0x%04X, payload=%s",
                                   address, rpc_id, payload)
            raise

    async def send_script(self, conn_id, data, progress_callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            data (bytes or bytearray): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
        """

        self._ensure_connection(conn_id, True)
        dev = self._get_property(conn_id, 'device')

        # Simulate some progress callbacks (0, 50%, 100%)
        progress_callback(0, len(data))
        progress_callback(len(data)//2, len(data))
        progress_callback(len(data), len(data))

        dev.script = data

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
            dev.stop()

    async def probe(self):
        """Send advertisements for all connected virtual devices."""

        for dev in self.devices.values():
            await self._send_scan_event(dev)
