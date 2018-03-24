import datetime
import logging
import msgpack
import tornado.gen
import tornado.ioloop
import tornado.websocket
from future.utils import viewitems
from builtins import bytes
from protocol import commands, operations


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    """Handle a WebSocket connection to multiple devices (v2)."""

    def __init__(self, application, request, **kwargs):
        super(WebSocketHandler, self).__init__(application, request, **kwargs)

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # TODO: remove this line
        self.logger.addHandler(logging.NullHandler())

        self.connections = {}

    def initialize(self, manager):
        self.manager = manager

    @classmethod
    def decode_datetime(cls, obj):
        """Decode a msgpack'ed datetime."""

        if b'__datetime__' in obj:
            obj = datetime.datetime.strptime(obj[b'as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        """Encode a msgpack'ed datetime."""

        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f").encode()}
        return obj

    @classmethod
    def _uuid_to_connection_string(cls, uuid):
        return str(uuid)

    @classmethod
    def _connection_string_to_uuid(cls, connection_string):
        return int(connection_string)

    def _get_connection_data(self, connection_string):
        if connection_string not in self.connections:
            self.logger.warn('No connection found for connection_string={}'.format(connection_string))
            return None

        return self.connections[connection_string]

    def _get_connection_id(self, connection_string):
        data = self._get_connection_data(connection_string)

        if data is None:
            return None

        return data['connection_id']

    def open(self, *args):
        self.set_nodelay(True)
        self.logger.info('Client connected')

    def send_response(self, operation, **kwargs):
        """Send a command response indicating it has been executed with success.
        Args:
            operation (str): The name of the operation which asked for a response
            **kwargs (str): Data to send with the response
        """

        response = dict({
            'type': 'response',
            'success': True,
            'operation': operation},
            **kwargs
        )

        self.logger.debug('Sending response: {}'.format(response))
        self._send_message(response)

    def send_notification(self, operation, **kwargs):
        """Send a notification (meaning a 'unexpected' message from the server to the client).
        Args:
            operation(str): The name of the operation matching the notification
            **kwargs: Data to send with the notification
        """

        notification = dict({
            'type': 'notification',
            'operation': operation},
            **kwargs
        )

        self.logger.debug('Sending notification ({}): {}'.format(operation, notification))
        self._send_message(notification)

    def send_error(self, operation, failure_reason, **kwargs):
        """Send an error message containing the failure reason
        Args:
            operation (str): The name of the operation which triggered the error
            failure_reason (str): The reason of the failure
            **kwargs: Data to send with the report chunk
        """

        error = dict({
            'type': 'response',
            'operation': operation,
            'success': False,
            'failure_reason': failure_reason},
            **kwargs
        )

        self.logger.error('Sending error: {}'.format(error))
        self._send_message(error)

    def _send_message(self, payload):
        """Send a binary message to the WebSocket connected client, after having msgpack'ed it

        Args:
            payload (dict): Data to send
        """

        message = msgpack.packb(payload, use_bin_type=True, default=self.encode_datetime)
        try:
            self.write_message(message, binary=True)
        except tornado.websocket.WebSocketClosedError:
            pass

    @tornado.gen.coroutine
    def on_message(self, message):
        try:

            message = msgpack.unpackb(message, raw=False, object_hook=self.decode_datetime)

            connection_string = message.get('connection_string', None)

            if commands.Scan.matches(message):
                devices = yield self.manager.probe_async()
                self._send_scan_result(devices)

            elif commands.Connect.matches(message):
                yield self._connect_to_device(connection_string)

            elif commands.Disconnect.matches(message):
                yield self._disconnect_from_device(connection_string)

            elif commands.OpenInterface.matches(message):
                yield self._open_interface(connection_string, message['interface'])

            elif commands.CloseInterface.matches(message):
                yield self._close_interface(connection_string, message['interface'])

            elif commands.SendRPC.matches(message):
                yield self._send_rpc(
                    connection_string,
                    message['address'],
                    message['rpc_id'],
                    message['payload'],
                    message['timeout']
                )

            elif commands.SendScript.matches(message):
                self._send_script(
                    connection_string,
                    message['script'],
                    (message['fragment_index'], message['fragment_count'])
                )

            else:
                self.send_error(
                    message.get('operation', operations.UNKNOWN),
                    'Received command not supported: {}'.format(message)
                )

        except Exception as err:
            self.logger.exception('Error while handling received message')
            self.send_error(operations.UNKNOWN, 'Exception raised: {}'.format(err))

    def _send_scan_result(self, devices):
        for uuid, info in viewitems(devices):
            connection_string = self._uuid_to_connection_string(uuid)
            converted_device = {
                'uuid': uuid,
                'user_connected': info.get('user_connected', False) or connection_string in self.connections,
                'connection_string': connection_string,
                'signal_strength': info['signal_strength'],
            }

            self.send_notification(operations.NOTIFY_DEVICE_FOUND, device=converted_device)

        self.send_response(operations.SCAN)

    @tornado.gen.coroutine
    def _connect_to_device(self, connection_string):
        operation = operations.CONNECT
        error = None

        if connection_string in self.connections:
            error = 'Already connected to this device: {}'.format(connection_string)

        else:
            uuid = self._connection_string_to_uuid(connection_string)
            result = yield self.manager.connect(uuid)

            if result['success']:
                self.connections[connection_string] = {
                    'connection_id': result['connection_id'],
                    'script': bytes(),
                    'report_monitor': self.manager.register_monitor(uuid, ['report'], self._notify_report),
                    'trace_monitor': self.manager.register_monitor(uuid, ['trace'], self._notify_trace)
                }

            else:
                error = result['reason']

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    @tornado.gen.coroutine
    def _disconnect_from_device(self, connection_string):
        operation = operations.DISCONNECT
        connection_id = self._get_connection_id(connection_string)

        error = None

        if connection_id is not None:
            result = yield self.manager.disconnect(connection_id)

            if result['success']:
                yield self._close_connection(connection_string)

            else:
                error = result['reason']
        else:
            error = 'Disconnection when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    @tornado.gen.coroutine
    def _open_interface(self, connection_string, interface):
        operation = operations.OPEN_INTERFACE
        connection_id = self._get_connection_id(connection_string)

        error = None

        if connection_id is not None:
            result = yield self.manager.open_interface(connection_id, interface)

            if not result['success']:
                error = 'An error occurred while opening interface: {}'.format(result['reason'])
        else:
            error = 'Attempt to open IOTile interface when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    @tornado.gen.coroutine
    def _close_interface(self, connection_string, interface):
        operation = operations.CLOSE_INTERFACE
        connection_id = self._get_connection_id(connection_string)

        error = None

        if connection_id is not None:
            result = yield self.manager.close_interface(connection_id, interface)

            if not result['success']:
                error = 'An error occurred while closing interface: {}'.format(result['reason'])
        else:
            error = 'Attempt to open IOTile interface when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    @tornado.gen.coroutine
    def _send_rpc(self, connection_string, address, rpc_id, payload, timeout):
        operation = operations.SEND_RPC
        connection_id = self._get_connection_id(connection_string)

        error = None
        return_value = None
        status = None

        if connection_id is not None:
            feature = rpc_id >> 8
            command = rpc_id & 0xFF
            result = yield self.manager.send_rpc(
                connection_id,
                address,
                feature,
                command,
                str(payload),
                timeout
            )

            if result['success']:
                return_value = result['payload']
                status = result['status']
            else:
                error = result['reason']
        else:
            error = 'Attempt to send an RPC when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string, return_value=return_value, status=status)

    @tornado.gen.coroutine
    def _send_script(self, connection_string, chunk, chunk_status):
        operation = operations.SEND_SCRIPT

        connection_data = self._get_connection_data(connection_string)
        if connection_data is None:
            self.send_error(operation, 'Received script chunk from unknown connection: {}'.format(connection_string))
            return

        # Check and see if we have the entire script or if we need to accumulate it
        index, count = chunk_status
        if index == 0:
            connection_data['script'] = bytes()

        connection_data['script'] += chunk

        # If there is more than one chunk and we aren't on the last one, wait until we receive them
        # all before sending them on to the device as a unit
        if index != count - 1:
            return

        error = None

        try:
            result = yield self.manager.send_script(
                connection_data['connection_id'],
                connection_data['script'],
                lambda x, y: self._notify_progress_async(tornado.ioloop.IOLoop.current(), connection_string, x, y)
            )
            connection_data['script'] = bytes()

            if not result['success']:
                error = result['reason']

        except Exception as exc:
            self.logger.exception('Error in manager send_script')
            error = 'Internal error: {}'.format(str(exc))

        if error:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    def _notify_progress_async(self, loop, connection_string, done_count, total_count):
        loop.add_callback(self._notify_progress_sync, connection_string, done_count, total_count)

    def _notify_progress_sync(self, connection_string, done_count, total_count):
        self.send_notification(
            operations.NOTIFY_PROGRESS,
            connection_string=connection_string,
            done_count=done_count,
            total_count=total_count
        )

    def _notify_report(self, device_uuid, event_name, report):
        connection_string = self._uuid_to_connection_string(device_uuid)

        if connection_string not in self.connections:
            self.logger.debug("Dropping report for device without an active connection: uuid={}".format(device_uuid))
            return

        self.send_notification(
            operations.NOTIFY_REPORT,
            connection_string=connection_string,
            payload=bytes(report.encode())
        )

    def _notify_trace(self, device_uuid, event_name, trace):
        connection_string = self._uuid_to_connection_string(device_uuid)

        if connection_string not in self.connections:
            self.logger.debug("Dropping trace for device without an active connection: uuid={}".format(device_uuid))
            return

        self.send_notification(operations.NOTIFY_TRACE, connection_string=connection_string, payload=trace)

    @tornado.gen.coroutine
    def _close_connection(self, connection_string):
        connection_data = self._get_connection_data(connection_string)

        if connection_data['connection_id'] is not None:
            yield self.manager.disconnect(connection_data['connection_id'])

        if connection_data['report_monitor'] is not None:
            self.manager.remove_monitor(connection_data['report_monitor'])

        del self.connections[connection_string]
        self.logger.debug('Connection closed with device, connection_string={}'.format(connection_string))

    @tornado.gen.coroutine
    def on_close(self):
        for connection_string in list(self.connections.keys()):
            yield self._close_connection(connection_string)

        self.logger.info('Client disconnected')
