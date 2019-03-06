# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import base64
import datetime
import logging
import msgpack
import tornado.gen
import tornado.ioloop
import tornado.websocket
from .protocol import commands, operations


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    """Handle a WebSocket connection to multiple devices (v2)."""

    def __init__(self, application, request, **kwargs):
        super(WebSocketHandler, self).__init__(application, request, **kwargs)

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # TODO: remove this line
        self.logger.addHandler(logging.NullHandler())

        self.connections = {}

    def initialize(self, manager, loop):
        """Initialize socket handler. Called every time a client call the websocket server
        address (cf gateway_agent.py). Used to get the DeviceManager of the gateway.
        /!\ : called before __init__

        Args:
            manager (DeviceManager): The device manager of the gateway.
            loop (tornado.ioloop): The event loop of the thread
        """

        self.manager = manager
        self.loop = loop

    @classmethod
    def decode_datetime(cls, obj):
        """Decode a msgpack'ed datetime."""
        if '__datetime__' in obj:
            obj = datetime.datetime.strptime(obj['as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        """Encode a msgpack'ed datetime."""

        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f").encode()}
        return obj

    @classmethod
    def _uuid_to_connection_string(cls, uuid):
        """Get the connection string from the uuid of a device.

        Args:
            uuid (int): The unique identifier of the device

        Returns:
            connection_string (str): The connection string designing the same device as the given uuid
        """

        return str(uuid)

    @classmethod
    def _connection_string_to_uuid(cls, connection_string):
        """Get the uuid of a device from a connection string.

        Args:
            connection_string (str): The connection string (probably received from external script)

        Returns:
            uuid (int): The unique identifier of the device
        """

        return int(connection_string)

    def _get_connection_data(self, connection_string):
        """Get all connection data from the connection string.

        Args:
            connection_string (str): The connection string (probably received from external script)

        Returns:
            data (dict): The connection data (contains connection_id, monitors, ...)
        """

        if connection_string not in self.connections:
            self.logger.warn('No connection found for connection_string={}'.format(connection_string))
            return None

        return self.connections[connection_string]

    def _get_connection_id(self, connection_string):
        """Get the connection id (meaning a id to identify the connection only from this side)
        from the connection string.

        Args:
            connection_string (str): The connection string (probably received from external script)

        Returns:
            connection_id (int): The connection id
        """

        data = self._get_connection_data(connection_string)

        if data is None:
            return None

        return data['connection_id']

    def open(self, *args):
        """Called when a client connects on the WebSocket server."""

        self.set_nodelay(True)  # To not buffer small messages, and send them immediately
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
        """Callback function called when a message is received on the WebSocket server.

        Args:
            message (bytes): The raw received message (msgpack'ed)
        """

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
        """Send scan results by sending one notification per device found and, at the end, a final response
        indicating than the scan is done.

        Args:
            devices (dict): The scanned devices to send (uuid as key, multiple info as value)
        """

        for uuid, info in devices.items():
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
        """Connect to the device matching the given connection_string.

        Args:
            connection_string (str): The connection string of the device to connect to.
        """

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
        """Disconnect from the device matching the given connection_string and properly close the connection.

        Args:
            connection_string (str): The connection string of the device to disconnect from.
        """

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
        """Open a given interface on the device matching the connection_string given.

        Args:
            connection_string (str): The identifier (connection_string) of the connection
            interface (str): The name of the interface to open
        """

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
        """Close a given interface on the device matching the connection_string given.

        Args:
            connection_string (str): The identifier (connection_string) of the connection
            interface (str): The name of the interface to close
        """

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
        """Send an RPC to the IOTile device matching the given connection_string.

        Args:
            connection_string (str): The connection string of the device
            address (int): the address of the tile that you want to talk to
            rpc_id (int): ID of the RPC to send
            payload (str): the payload to send (up to 20 bytes), encoded using base64
        """

        operation = operations.SEND_RPC
        connection_id = self._get_connection_id(connection_string)

        error = None
        return_value = None
        status = None

        if connection_id is not None:
            feature = rpc_id >> 8  # Calculate the feature value from RPC id
            command = rpc_id & 0xFF  # Calculate the command value from RPC id
            decoded_payload = base64.b64decode(payload)

            result = yield self.manager.send_rpc(
                connection_id,
                address,
                feature,
                command,
                decoded_payload,
                timeout
            )

            if result['success']:
                return_value = base64.b64encode(result['payload'])
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
        """Send a script to the device matching the given connection_string. Wait for receiving all chunks
        before sending it to the device.

        Args:
            connection_string (str): The connection string of the device
            chunk (str): A chunk of the script to send (up to 20 bytes), encoded using base64
            chunk_status (tuple): Contains information as the current chunk index and the total of chunk which
                                compose the script.
        """

        operation = operations.SEND_SCRIPT

        connection_data = self._get_connection_data(connection_string)
        if connection_data is None:
            self.send_error(operation, 'Received script chunk from unknown connection: {}'.format(connection_string))
            return

        # Check and see if we have the entire script or if we need to accumulate it
        index, count = chunk_status
        if index == 0:
            connection_data['script'] = bytes()

        decoded_chunk = base64.b64decode(chunk)
        connection_data['script'] += decoded_chunk

        # If there is more than one chunk and we aren't on the last one, wait until we receive them
        # all before sending them on to the device as a unit
        if index != count - 1:
            return

        error = None

        try:
            result = yield self.manager.send_script(
                connection_data['connection_id'],
                connection_data['script'],
                lambda x, y: self._notify_progress_async(connection_string, x, y)
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

    def _notify_progress_async(self, connection_string, done_count, total_count):
        """Add a synchronous notify progress function to the event loop.

        Args:
            connection_string (str): The connection string of the device where the operation is in progress
            done_count (int): Number of chunks already processed
            total_count (int): Number of total chunks to proceed
        """

        self.loop.add_callback(self._notify_progress_sync, connection_string, done_count, total_count)

    def _notify_progress_sync(self, connection_string, done_count, total_count):
        """Send a notification containing the current progress of the given operation. The progress is computed
        from done_count/total_count.

        Args:
            connection_string (str): The connection string of the device where the operation is in progress
            done_count (int): Number of chunks already processed
            total_count (int): Number of total chunks to proceed
        """

        self.send_notification(
            operations.NOTIFY_PROGRESS,
            connection_string=connection_string,
            done_count=done_count,
            total_count=total_count
        )

    def _notify_report(self, device_uuid, event_name, report):
        """Stream a report to the WebSocket client. Called by the report_monitor.

        Args:
            device_uuid (int): The uuid of the device which sent the report
            event_name: 'report'
            report (IOTileReport): The report to send.
        """

        connection_string = self._uuid_to_connection_string(device_uuid)

        if connection_string not in self.connections:
            self.logger.debug("Dropping report for device without an active connection: uuid={}".format(device_uuid))
            return

        self.send_notification(
            operations.NOTIFY_REPORT,
            connection_string=connection_string,
            payload=base64.b64encode(report.encode())
        )

    def _notify_trace(self, device_uuid, event_name, trace):
        """Stream tracing data to the WebSocket client. Called by the trace_monitor.

        Args:
            device_uuid (int): The uuid of the device which sent the report
            event_name: 'report'
            trace (bytes): The trace to send.
        """

        connection_string = self._uuid_to_connection_string(device_uuid)

        if connection_string not in self.connections:
            self.logger.debug("Dropping trace for device without an active connection: uuid={}".format(device_uuid))
            return

        self.send_notification(
            operations.NOTIFY_TRACE,
            connection_string=connection_string,
            payload=base64.b64encode(trace)
        )

    @tornado.gen.coroutine
    def _close_connection(self, connection_string):
        """Properly close a connection: disconnect client if still connected, remove monitors, remove connection data.

        Args:
            connection_string (str): The connection string of the device
        """

        connection_data = self._get_connection_data(connection_string)

        if connection_data['connection_id'] is not None:
            yield self.manager.disconnect(connection_data['connection_id'])

        if connection_data['report_monitor'] is not None:
            self.manager.remove_monitor(connection_data['report_monitor'])

        if connection_data['trace_monitor'] is not None:
            self.manager.remove_monitor(connection_data['trace_monitor'])

        del self.connections[connection_string]
        self.logger.debug('Connection closed with device, connection_string={}'.format(connection_string))

    @tornado.gen.coroutine
    def on_close(self):
        """Callback function called when a WebSocket client disconnects. We properly close all connections
        with the devices."""

        for connection_string in list(self.connections.keys()):
            yield self._close_connection(connection_string)

        self.logger.info('Client disconnected')
