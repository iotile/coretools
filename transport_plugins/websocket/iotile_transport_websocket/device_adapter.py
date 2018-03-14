from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.utilities.validating_wsclient import ValidatingWSClient
from iotile.core.exceptions import ArgumentError, HardwareError, TimeoutExpiredError
from connection_manager import ConnectionManager


class WebSocketDeviceAdapter(DeviceAdapter):
    """ A device adapter allowing connections to devices over websockets

    Args:
        url (string): A url for the websocket server in form of server:port/path
    """

    def __init__(self, port):
        super(WebSocketDeviceAdapter, self).__init__()

        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('probe_supported', True)
        self.set_config('probe_required', True)

        path = "ws://{0}/services".format(port)
        self.client = ValidatingWSClient(path)
        self.client.start()

        self.connections = ConnectionManager(self.id)
        self.connections.start()

    def connect_async(self, connection_id, connection_string, callback):
        """Connect to a device by its connection_string

        Args:
            connection_id (int): A unique integer set by the caller for referring to this connection
                once created
            connection_string (string): A device id of the form d--XXXX-YYYY-ZZZZ-WWWW
            callback (callable): A callback function called when the connection has succeeded or
                failed
        """

        context = {}
        self.connections.begin_connection(connection_id, connection_string, callback, context, self.get_config('default_timeout'))

        result = self.client.send_command('connect', {})
        print(result)
        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_connection(connection_id, result['success'], result.get('reason', None))

    def disconnect_async(self, connection_id, callback):
        """Asynchronously disconnect from a device that has previously been connected

        Args:
            connection_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): A function called as callback(conn_id, adapter_id, success, failure_reason)
            when the disconnection finishes.  Disconnection can only either succeed or timeout.
        """

        try:
            self.connections.get_connection_id(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_disconnection(connection_id, callback, self.get_config('default_timeout'))

        result = self.client.send_command('disconnect', {})
        print(result)
        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_disconnection(connection_id, result['success'], result.get('reason', None))

    def probe_async(self, callback):
        """Probe for visible devices connected to this DeviceAdapter.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        result = self.client.send_command('scan', {})
        if not result['success']:
            callback(self.id, False, 'Error while scanning through ws : {}'.format(result['reason']))
        else:
            # FIXME: async after creating WebSocketHandler2
            for dev in result['devices']:
                self._trigger_callback('on_scan', self.id, dev, self.get_config('expiration_time'))
            callback(self.id, True, None)

    def stop_sync(self):
        """Synchronously stop this adapter
        """

        connections = self.connections.get_connections()

        for connection in connections:
            try:
                self.disconnect_sync(connection)
            except HardwareError:
                pass

        self.client.stop()
        self.connections.stop()

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter."""

        pass
