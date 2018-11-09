import json
import os
import traceback
import imp
import inspect
import time
from future.utils import itervalues, viewitems
import pkg_resources
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.reports import BroadcastReport
from .adapter import DeviceAdapter
from ..virtual import (RPCInvalidIDError, TileNotFoundError, RPCNotFoundError,
                       VirtualIOTileDevice, RPCErrorCode)


class VirtualAdapterAsyncChannel(object):
    """A channel for tracing and streaming data asynchronously from virtual devices
    """

    def __init__(self, adapter, iotile_id):
        self.adapter = adapter
        self.iotile_id = iotile_id

    def stream(self, report, callback=None):
        """Queue data for streaming

        Args:
            report (IOTileReport): A report object to stream to a client
            callback (callable): An optional callback that will be called with
                a bool value of True when this report actually gets streamed.
                If the client disconnects and the report is dropped instead,
                callback will be called with False
        """

        conn_id = self._find_connection(self.iotile_id)

        if conn_id is not None or isinstance(report, BroadcastReport):
            self.adapter._trigger_callback('on_report', conn_id, report)

        if callback is not None:
            callback(conn_id is not None)

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

        conn_id = self._find_connection(self.iotile_id)

        if conn_id is not None:
            self.adapter._trigger_callback('on_trace', conn_id, data)

        if callback is not None:
            callback(conn_id is not None)

    def _find_connection(self, iotile_id):
        """Find the connection corresponding to an iotile_id
        """

        for conn_id, dev in viewitems(self.adapter.connections):
            if dev.iotile_id == iotile_id:
                return conn_id

        return None


class VirtualDeviceAdapter(DeviceAdapter):
    """Callback based adapter that gives access to one or more virtual devices

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
        super(VirtualDeviceAdapter, self).__init__()

        loaded_devs = {}

        if devices is None:
            devices = []

        # This needs to be initialized before any VirtualAdapterAsyncChannels are
        # created because those could reference it
        self.connections = {}

        if port is not None:
            devs = port.split(';')

            for dev in devs:
                name, _sep, config = dev.partition('@')

                if len(config) == 0:
                    config = None

                loaded_dev = self._load_device(name, config)

                if not self._validate_device(loaded_dev):
                    raise ArgumentError("Device type cannot be loaded on this adapter", name=name)

                loaded_dev.start(VirtualAdapterAsyncChannel(self, loaded_dev.iotile_id))
                loaded_devs[loaded_dev.iotile_id] = loaded_dev

        # Allow explicitly passing created VirtualDevice subclasses
        for dev in devices:
            if not self._validate_device(dev):
                raise ArgumentError("Device type cannot be loaded on this adapter", name=name)

            dev.start(VirtualAdapterAsyncChannel(self, dev.iotile_id))
            loaded_devs[dev.iotile_id] = dev

        self.devices = loaded_devs
        self.scan_interval = self.get_config('scan_interval', 1.0)
        self.last_scan = None

        self.set_config('probe_required', True)
        self.set_config('probe_supported', True)

    #pylint:disable=unused-argument;The name needs to remain without an _ for subclasses to override
    @classmethod
    def _validate_device(cls, device):
        """Hook for subclases to ensure that only specific kinds of devices are loaded.

        The default implementation just returns True, allowing all virtual devices.

        Returns:
            bool: Whether the virtual device is allowed to load.
        """

        return True

    @classmethod
    def _find_device_script(cls, script_path):
        """Import a virtual device from a file rather than an installed module

        script_path must point to a python file ending in .py that contains exactly one
        VirtualIOTileDevice class definitions.  That class is loaded and executed as if it
        were installed.

        Args:
            script_path (string): The path to the script to load

        Returns:
            VirtualIOTileDevice: A subclass of VirtualIOTileDevice that was loaded from script_path
        """

        search_dir, filename = os.path.split(script_path)
        if search_dir == '':
            search_dir = './'

        if filename == '' or not os.path.exists(script_path):
            raise ArgumentError("Could not find script to load virtual device", path=script_path)

        module_name, ext = os.path.splitext(filename)
        if ext != '.py':
            raise ArgumentError("Script did not end with .py", filename=filename)

        try:
            file = None
            file, pathname, desc = imp.find_module(module_name, [search_dir])
            mod = imp.load_module(module_name, file, pathname, desc)
        finally:
            if file is not None:
                file.close()

        devs = [x for x in itervalues(mod.__dict__) if inspect.isclass(x) and issubclass(x, VirtualIOTileDevice) and x != VirtualIOTileDevice]
        if len(devs) == 0:
            raise ArgumentError("No VirtualIOTileDevice subclasses were defined in script", path=script_path)
        elif len(devs) > 1:
            raise ArgumentError("More than one VirtualIOTileDevice subclass was defined in script", path=script_path, devices=devs)

        return devs[0]

    def _load_device(self, name, config):
        """Load a device either from a script or from an installed module
        """

        if config is None:
            config_dict = {}
        elif isinstance(config, dict):
            config_dict = config
        elif config[0] == '#':
            # Allow passing base64 encoded json directly in the port string to ease testing.
            import base64
            config_str = base64.b64decode(config[1:])
            config_dict = json.loads(config_str)
        else:
            try:
                with open(config, "r") as conf:
                    data = json.load(conf)
            except IOError as exc:
                raise ArgumentError("Could not open config file", error=str(exc), path=config)

            if 'device' not in data:
                raise ArgumentError("Invalid configuration file passed to VirtualDeviceAdapter", device_name=name, config_path=config, missing_key='device')

            config_dict = data['device']

        if name.endswith('.py'):
            device_factory = self._find_device_script(name)
            return device_factory(config_dict)

        seen_names = []
        for entry in pkg_resources.iter_entry_points('iotile.virtual_device'):
            if entry.name == name:
                device_factory = entry.load()
                return device_factory(config_dict)

            seen_names.append(entry.name)

        raise ArgumentError("Could not find virtual_device by name", name=name, known_names=seen_names)

    def can_connect(self):
        """Can this adapter have another simultaneous connection

        There is no limit on the number of simultaneous virtual connections

        Returns:
            bool: whether another connection is allowed
        """

        return True

    def connect_async(self, connection_id, connection_string, callback):
        """Asynchronously connect to a device

        Args:
            connection_id (int): A unique identifer that will refer to this connection
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.
            callback (callable): A function that will be called when the connection attempt finishes as
                callback(conection_id, adapter_id, success: bool, failure_reason: string or None)
        """

        id_number = int(connection_string)
        if id_number not in self.devices:
            if callback is not None:
                callback(connection_id, self.id, False, "could not find device to connect to")
            return

        if id_number in [x.iotile_id for x in itervalues(self.connections)]:
            if callback is not None:
                callback(connection_id, self.id, False, "device was already connected to")
            return

        dev = self.devices[id_number]
        dev.connected = True

        self.connections[connection_id] = dev

        if callback is not None:
            callback(connection_id, self.id, True, "")

    def disconnect_async(self, conn_id, callback):
        """Asynchronously disconnect from a connected device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, "device had no active connection")
            return

        dev = self.connections[conn_id]
        dev.connected = False
        del self.connections[conn_id]

        if callback is not None:
            callback(conn_id, self.id, True, "")

    def _open_rpc_interface(self, conn_id, callback):
        """Open the RPC interface on a device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, "device had no active connection")
            return

        dev = self.connections[conn_id]
        dev.open_rpc_interface()

        if callback is not None:
            callback(conn_id, self.id, True, "")

    def _open_streaming_interface(self, conn_id, callback):
        """Open the streaming interface on a device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, "device had no active connection")
            return

        dev = self.connections[conn_id]
        reports = dev.open_streaming_interface()

        if callback is not None:
            callback(conn_id, self.id, True, "")

        for report in reports:
            self._trigger_callback('on_report', conn_id, report)

    def _open_tracing_interface(self, conn_id, callback):
        """Open the tracing interface on a device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, "device had no active connection")

            return

        dev = self.connections[conn_id]
        traces = dev.open_tracing_interface()

        if callback is not None:
            callback(conn_id, self.id, True, "")

        for trace in traces:
            self._trigger_callback('on_trace', conn_id, trace)

    def _open_script_interface(self, conn_id, callback):
        """Open the script interface on a device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, "device had no active connection")
            return

        dev = self.connections[conn_id]
        dev.open_script_interface()

        if callback is not None:
            callback(conn_id, self.id, True, "")

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, 'Device is not in connected state', None, None)
            return

        dev = self.connections[conn_id]

        status = (1 << 6)
        try:
            response = bytes()
            response = dev.call_rpc(address, rpc_id, bytes(payload))
            if len(response) > 0:
                status |= (1 << 7)
        except (RPCInvalidIDError, RPCNotFoundError):
            status = 2
        except TileNotFoundError:
            status = 0xFF
        except RPCErrorCode as exc:
            status |= exc.params['code'] & ((1 << 6) - 1)
        except Exception:
            #Don't allow exceptions or we will deadlock
            status = 3

            print("*** EXCEPTION OCCURRED IN RPC ***")
            traceback.print_exc()
            print("*** END EXCEPTION ***")

        response = bytearray(response)
        callback(conn_id, self.id, True, "", status, response)

    def send_script_async(self, conn_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (bytes or bytearray): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        if conn_id not in self.connections:
            if callback is not None:
                callback(conn_id, self.id, False, 'Device is not in connected state')
            return

        # Simulate some progress callbacks (0, 50%, 100%)
        progress_callback(0, len(data))
        dev = self.connections[conn_id]
        dev.script = data
        progress_callback(len(data)//2, len(data))
        progress_callback(len(data), len(data))

        callback(conn_id, self.id, True, None)

    def _send_scan_event(self, device):
        """Send a scan event from a device
        """

        info = {
            'connection_string': str(device.iotile_id),
            'uuid': device.iotile_id,
            'signal_strength': 100
        }
        self._trigger_callback('on_scan', self.id, info, self.ExpirationTime)

    def periodic_callback(self):
        if self.last_scan is None or time.time() > (self.scan_interval + self.last_scan):
            for dev in itervalues(self.devices):
                self._send_scan_event(dev)

    def stop_sync(self):
        for dev in itervalues(self.devices):
            dev.stop()

    def probe_async(self, callback):
        """Send advertisements for all connected virtual devices.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        for dev in itervalues(self.devices):
            self._send_scan_event(dev)

        callback(self.id, True, None)
