from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.utilities.validating_wsclient import ValidatingWSClient
from iotile.core.exceptions import ArgumentError, HardwareError, TimeoutExpiredError
from connection_manager import ConnectionManager


class WebSocketDeviceAdapter(DeviceAdapter):
    """ A device adapter allowing connections to devices over websockets

    Args:
        url (string): A url for the websocket server in form of server:port/path
    """

    def __init__(self, url):
        super(WebSocketDeviceAdapter, self).__init__()

        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('probe_supported', True)
        self.set_config('probe_required', True)

        path = "ws://{0}".format(url)
        self.client = ValidatingWSClient(path)
        self.client.start()

        self.connections = ConnectionManager(self.id)
        self.connections.start()

    def connect_async(self, connection_id, connection_string, callback):
        print(connection_id, connection_string)
        context = {}
        self.connections.begin_connection(connection_id, connection_string, callback, context, self.get_config('default_timeout'))

        result = self.client.send_command('connect', {})
        print(result)
        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_connection(connection_id, result['success'], result.get('reason', None))

    def disconnect_async(self, connection_id, callback):
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
        result = self.client.send_command('scan', {})
        if not result['success']:
            callback(self.id, False, 'Error while scanning through ws : {}'.format(result['reason']))
        else:
            # FIXME: async after creating WebSocketHandler2
            for dev in result['devices']:
                self._trigger_callback('on_scan', self.id, dev, self.get_config('expiration_time'))
            callback(self.id, True, None)

    def stop_sync(self):
        connections = self.connections.get_connections()

        for connection in connections:
            try:
                self.disconnect_sync(connection)
            except HardwareError:
                pass

        self.client.stop()
        self.connections.stop()

    def periodic_callback(self):
        try:
            self.client.send_command('ping', {})
        except TimeoutExpiredError:
            self.logger.error('No more connected to the websocket server. Stopping all...')
            connections = self.connections.get_connections()

            for connection in connections:
                self.connections.unexpected_disconnect(connection)

            self.client.stop()
