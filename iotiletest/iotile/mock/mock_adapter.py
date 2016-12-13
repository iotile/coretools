"""A mock DeviceAdapter that just connects to a python MockIOTileDevice
"""
from iotile.core.hw.transport.adapter import DeviceAdapter
from mock_iotile import RPCInvalidIDError, TileNotFoundError, RPCNotFoundError

class MockDeviceAdapter(DeviceAdapter):
    """A mock DeviceAdapter that connects to one or more python MockIOTileDevices
    """

    def __init__(self):
        self.devices = {}
        self.connections = {}

        super(MockDeviceAdapter, self).__init__()

    def add_device(self, conn_string, device):
        self.devices[conn_string] = device

    def can_connect(self):
        return True

    def advertise(self):
        for conn_string, device in self.devices.iteritems():
            info = {'uuid': device.iotile_id, 'connection_string': conn_string, 'signal_strength': 0}
            self._trigger_callback('on_scan', self.id, info, 0)

    def connect_async(self, connection_id, connection_string, callback):
        if connection_string not in self.devices:
            callback(connection_id, self.id, False, "Could not find device connection string")
            return

        self.connections[connection_id] = self.devices[connection_string]
        callback(connection_id, self.id, True, "")

    def disconnect_async(self, connection_id, callback):
        if connection_id not in self.connections:
            callback(connection_id, self.id, False, "Could not find connection id to disconnect")
            return

        del self.connections[connection_id]
        callback(connection_id, self.id, True, "")

    def _open_rpc_interface(self, connection_id, callback):
        if connection_id not in self.connections:
            callback(connection_id, self.id, False, "Could not find connection id to disconnect")
            return

        device = self.connections[connection_id]
        device.open_rpc_interface()
        
        callback(connection_id, self.id, True, "")

    def _open_script_interface(self, connection_id, callback):
        if connection_id not in self.connections:
            callback(connection_id, self.id, False, "Could not find connection id to disconnect")
            return

        device = self.connections[connection_id]
        device.open_script_interface()
        
        callback(connection_id, self.id, True, "")

    def _open_streaming_interface(self, connection_id, callback):
        if connection_id not in self.connections:
            callback(connection_id, self.id, False, "Could not find connection id to disconnect")
            return

        device = self.connections[connection_id]
        reports = device.open_streaming_interface()
        
        callback(connection_id, self.id, True, "")

        for report in reports:
            self._trigger_callback('on_report', connection_id, report)

    def send_rpc_async(self, connection_id, address, rpc_id, payload, timeout, callback):
        status = 0x00

        if connection_id not in self.connections:
            callback(connection_id, self.id, False, "Could not find connection id to send rpc", None, None)
            return

        device = self.connections[connection_id]

        try:
            payload = device.call_rpc(address, rpc_id, payload)
        except (RPCInvalidIDError, RPCNotFoundError):
            status = 0x03
        except TileNotFoundError:
            status = 0xFF

        if status == 0 and len(payload) > 0:
            status = 0xC0
        elif status == 0:
            status = 0x40

        callback(connection_id, self.id, True, "", status, payload)

    def send_script_async(self, connection_id, data, progress_callback, callback):
        if connection_id not in self.connections:
            callback(connection_id, self.id, False, "Could not find connection id to send script")
            return

        device = self.connections[connection_id]

        for i in xrange(0, len(data), 20):
            device.push_script_chunk(data[i:i+20])
            progress_callback(min(i+20, len(data)), len(data))

        callback(connection_id, self.id, True, "")

    def stop_sync(self):
        pass

    def periodic_callback(self):
        pass
