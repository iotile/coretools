# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import base64
import datetime
import logging
import msgpack
import threading
import time
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.exceptions import HardwareError
from .websocket_server import WebsocketServer
from .protocol import commands, operations


class WebSocketVirtualInterface(VirtualIOTileInterface):
    """ Run a simple WebSocket server and provide a virtual interface between it and a virtual device.

    Args:
        args (dict): A dictionary of arguments used to configure this interface.
            Supported args are:

                port (int):
                    The port on which the server will listen (default: 5120)

    """
    def __init__(self, args):
        super(WebSocketVirtualInterface, self).__init__()

        if 'port' in args:
            port = int(args['port'])
        else:
            port = 5120

        self.chunk_size = 4*1024  # Config chunk size to be 4kb for traces and reports streaming

        # Set logger
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

        # Initialize states
        # - Interfaces
        self.rpc_enabled = False
        self.streaming_enabled = False
        self.tracing_enabled = False
        self.script_enabled = False
        self.debug_enabled = False
        # - Current action
        self.streaming_data = False
        self.tracing_data = False

        # WebSocket client
        self.client = None

        # WebSocket server
        self.server = WebsocketServer(port, host='127.0.0.1', loglevel=logging.DEBUG)
        self.server.set_fn_new_client(self.on_new_client)
        self.server.set_fn_client_left(self.on_client_disconnect)
        self.server.set_fn_message_received(self.on_message)

        self.server_thread = threading.Thread(
            target=self.server.run_forever,
            name='WebSocketVirtualServer'
        )

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
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%fZ").encode()}
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

    def _get_connection_id(self, connection_string):
        """Get the connection id (meaning a id to identify the connection only from this side)
        from the connection string.

        Args:
            connection_string (str): The connection string (probably received from external script)

        Returns:
            connection_id (int): The connection id
        """

        if self.device is None or not self.device.connected:
            return None

        return int(connection_string)

    def start(self, device):
        """Start serving access to this VirtualIOTileDevice

        Args:
            device (VirtualIOTileDevice): The device we will be providing access to
        """

        super(WebSocketVirtualInterface, self).start(device)

        self.server_thread.start()

    def process(self):
        """Periodic nonblocking processes. Used to check if there are reports or traces to send."""

        super(WebSocketVirtualInterface, self).process()

        if (not self.streaming_data) and (not self.reports.empty()):
            self._stream_data(self.device.iotile_id)

        if (not self.tracing_data) and (not self.traces.empty()):
            self._send_trace(self.device.iotile_id)

    def on_new_client(self, client, server):
        """Callback function called when a WebSocket client connects on the server.

        Args:
            client (dict): A dictionary containing client information
                id (int):
                    A unique client ID
                address (tuple):
                    Tuple containing (client IP address, client port)
                handler (WebSocketHandler):
                    An instance of the websocket handler (which is a stream to send/receive messages)

            server (WebsocketServer): The server instance
        """

        self.logger.info('Client connected with id {}'.format(client['id']))
        self.client = client

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
            payload (dict): data to send
        """

        try:
            message = msgpack.packb(payload, use_bin_type=True, default=self.encode_datetime)
            self.server.send_message(self.client, message, binary=True)
        except Exception as err:
            self.logger.exception(err)

    def on_message(self, client, server, message):
        """Callback function called when a message is received on the WebSocket server.

        Args:
            client (dict): A dictionary containing client information
                id (int):
                    A unique client ID
                address (tuple):
                    Tuple containing (client IP address, client port)
                handler (WebSocketHandler):
                    An instance of the websocket handler (which is a stream to send/receive messages)

            server (WebsocketServer): The server instance
            message (bytes): The raw received message (msgpack'ed)
        """

        try:
            message = msgpack.unpackb(message, raw=False, object_hook=self.decode_datetime)

            connection_string = message.get('connection_string', None)

            if commands.Scan.matches(message):
                devices = self._simulate_scan_response()
                self._send_scan_result(devices)

            elif commands.Connect.matches(message):
                self._connect_to_device(connection_string)

            elif commands.Disconnect.matches(message):
                self._disconnect_from_device(connection_string)

            elif commands.OpenInterface.matches(message):
                self._open_interface(connection_string, message['interface'])

            elif commands.CloseInterface.matches(message):
                self._close_interface(connection_string, message['interface'])

            elif commands.SendRPC.matches(message):
                self._send_rpc(
                    connection_string,
                    message['address'],
                    message['rpc_id'],
                    message['payload']
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

    def _simulate_scan_response(self):
        """Return a dict containing the virtual device information to simulate a scan response."""

        return {
            self.device.iotile_id: {
                'connection_string': self.device.iotile_id,
                'pending_data': self.device.pending_data,
                'name': self.device.name,
                'connected': self.device.connected,
                'uuid': self.device.iotile_id,
                'signal_strength': 0
            }
        }

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
                'user_connected': 'user_connected' in info,
                'connection_string': connection_string,
                'signal_strength': info['signal_strength'],
            }

            self.send_notification(operations.NOTIFY_DEVICE_FOUND, device=converted_device)

        self.send_response(operations.SCAN)

    def _connect_to_device(self, connection_string):
        """Connect to the device matching the given connection_string.

        Args:
            connection_string (str): The connection string of the device to connect to.
        """

        operation = operations.CONNECT
        error = None

        if self.device.connected:
            error = 'Already connected to this device: {}'.format(connection_string)

        else:
            uuid = self._connection_string_to_uuid(connection_string)
            if uuid != self.device.iotile_id:
                error = 'Unknown device with uuid={}'.format(uuid)
            else:
                # For virtual device, we simulate connection
                self.device.connected = True
                self._audit('ClientConnected')

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    def _disconnect_from_device(self, connection_string):
        """Disconnect from the device matching the given connection_string after cleaning it.

        Args:
            connection_string (str): The connection string of the device to disconnect from.
        """

        operation = operations.DISCONNECT
        connection_id = self._get_connection_id(connection_string)

        error = None

        if connection_id is not None:
            self.clean_device()
            # For virtual device, we simulate disconnection
            self.device.connected = False
            self._audit('ClientDisconnected')
        else:
            error = 'Disconnection when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    def _simulate_open_interface(self, connection_id, interface):
        """Simulate opening a given interface on a device, with same inputs as the real open_interface method
        in DeviceManager, but use a virtual device instead.

        Args:
            connection_id (int): The identifier of the connection used only from this side
            interface (str): The name of the interface
        """

        error = None

        # If device not connected or try to open interface on wrong device: error
        if not self.device.connected:
            error = 'Not connected to the device'
        elif connection_id != self.device.iotile_id:
            error = 'Wrong connection id: given={}, known={}'.format(connection_id, self.device.iotile_id)

        if error is None:
            if interface == 'rpc':
                if self.rpc_enabled:
                    error = 'RPC interface already opened'
                else:
                    self.rpc_enabled = True
                    self.device.open_rpc_interface()
                    self._audit('RPCInterfaceOpened')

            elif interface == 'streaming':
                if self.streaming_enabled:
                    error = 'Streaming interface already opened'
                else:
                    self.streaming_enabled = True
                    reports = self.device.open_streaming_interface()
                    if reports is not None:
                        self._queue_reports(*reports)
                    self._audit('StreamingInterfaceOpened')

            elif interface == 'tracing':
                if self.tracing_enabled:
                    error = 'Tracing interface already opened'
                else:
                    self.tracing_enabled = True
                    traces = self.device.open_tracing_interface()
                    if traces is not None:
                        self._queue_traces(*traces)
                    self._audit('TracingInterfaceOpened')

            elif interface == 'script':
                if self.script_enabled:
                    error = 'Script interface already opened'
                else:
                    self.script_enabled = True
                    self.device.open_script_interface()
                    self._audit('ScriptInterfaceOpened')

            elif interface == 'debug':
                if self.debug_enabled:
                    error = 'Debug interface already opened'
                else:
                    self.debug_enabled = True
                    self.device.open_debug_interface()
                    self._audit('DebugInterfaceOpened')

            else:
                error = 'Unknown interface received: {}'.format(interface)

        result = {
            'success': error is None
        }
        if error is not None:
            result['reason'] = error

        return result

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
            result = self._simulate_open_interface(connection_id, interface)

            if not result['success']:
                error = 'An error occurred while opening interface: {}'.format(result['reason'])
        else:
            error = 'Attempt to open IOTile interface when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    def _simulate_close_interface(self, connection_id, interface):
        """Simulate closing a given interface on a device, with same inputs as the real close_interface method
        in DeviceManager, but use a virtual device instead.

        Args:
            connection_id (int): The identifier of the connection used only from this side
            interface (str): The name of the interface
        """

        error = None

        # If device not connected or try to open interface on wrong device: error
        if not self.device.connected:
            error = 'Not connected to the device'
        elif connection_id != self.device.iotile_id:
            error = 'Wrong connection id: given={}, known={}'.format(connection_id, self.device.iotile_id)

        if error is None:
            if interface == 'rpc':
                if self.rpc_enabled:
                    self.device.close_rpc_interface()
                    self._audit('RPCInterfaceClosed')
                else:
                    error = 'RPC interface already closed'

            elif interface == 'streaming':
                if self.streaming_enabled:
                    self.streaming_enabled = False
                    self.device.close_streaming_interface()
                    self._audit('StreamingInterfaceClosed')
                else:
                    error = 'Streaming interface already closed'

            elif interface == 'tracing':
                if self.tracing_enabled:
                    self.tracing_enabled = False
                    self.device.close_tracing_interface()
                    self._audit('TracingInterfaceClosed')
                else:
                    error = 'Tracing interface already closed'

            elif interface == 'script':
                if self.script_enabled:
                    self.script_enabled = False
                    self.device.close_script_interface()
                    self._audit('ScriptInterfaceClosed')
                else:
                    error = 'Script interface already closed'

            elif interface == 'debug':
                if self.debug_enabled:
                    self.debug_enabled = False
                    self.device.close_debug_interface()
                    self._audit('DebugInterfaceClosed')
                else:
                    error = 'Debug interface already closed'

            else:
                error = 'Unknown interface received: {}'.format(interface)

        result = {
            'success': error is None
        }
        if error is not None:
            result['reason'] = error

        return result

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
            result = self._simulate_close_interface(connection_id, interface)

            if not result['success']:
                error = 'An error occurred while closing interface: {}'.format(result['reason'])
        else:
            error = 'Attempt to close IOTile interface when there was no connection'

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    def _simulate_send_rpc(self, connection_id, address, feature, command, payload):
        """Simulate sending an RPC to an IOTile device, with same inputs as the real send_rpc method
        in DeviceManager, but use a virtual device instead.

        Args:
            connection_id (int): The connection id returned from a previous call to connect()
            address (int): the address of the tile that you want to talk to
            feature (int): the high byte of the rpc id
            command (int): the low byte of the rpc id
            payload (string): the payload to send (up to 20 bytes)

        Returns:
            result (dict): The result of the operation. Contains:
                status (int): Status code of the result
                payload (any): The result returned by the RPC
        """

        error = None

        if not self.device.connected:
            error = 'Not connected to the device'
        elif connection_id != self.device.iotile_id:
            error = 'Wrong connection id: given={}, known={}'.format(connection_id, self.device.iotile_id)
        elif not self.rpc_enabled:
            error = 'Try to send RPC when RPC interface is closed'

        return_value = None
        status = None

        if error is None:
            rpc_id = (feature << 8) | command  # Calculate the RPC id from the feature and the command values

            try:
                return_value = self.device.call_rpc(address, rpc_id, payload)
                status = (1 << 7)  # RPC executed with success
                if len(return_value) > 0:
                    status |= (1 << 6)  # RPC returned data that should be read

            except (RPCInvalidIDError, RPCNotFoundError):
                status = (1 << 1)  # Indicates RPC address or id not correct
                return_value = b''
            except TileNotFoundError:
                status = 0xFF  # Indicates RPC had an error
                return_value = b''

        result = {
            'success': error is None
        }
        if error is None:
            result['payload'] = return_value
            result['status'] = status
        else:
            result['reason'] = error

        return result

    def _send_rpc(self, connection_string, address, rpc_id, payload):
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

            result = self._simulate_send_rpc(
                connection_id,
                address,
                feature,
                command,
                decoded_payload
            )

            if result['success']:
                return_value = base64.b64encode(result['payload'])
                status = result['status']
            else:
                error = result['reason']
        else:
            error = 'Attempt to send an RPC when there was no connection'

        self._audit("RPCReceived",
                    rpc_id=rpc_id,
                    address=address,
                    payload=payload,
                    status=status,
                    response=return_value)

        if error is not None:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string, return_value=return_value, status=status)

    def _simulate_send_script(self, connection_id, script, progress_callback):
        """Simulate sending a script to an IOTile device, with same inputs as the real send_rpc method
        in DeviceManager, but use a virtual device instead.

        Args:
            connection_id (int): The connection id returned from a previous call to connect()
            script (bytes): The whole script to send to the device
            progress_callback (func): A callback to call to indicate the progress of the script upload.
                Must be called like progress_callback(connection_string, done_count, total_count)
        """

        connection_string = self._uuid_to_connection_string(connection_id)

        script_length = len(script)
        total_count = script_length // self.chunk_size
        if script_length % self.chunk_size != 0:
            total_count += 1

        for index in range(total_count):
            first_index = index * self.chunk_size
            last_index = min(first_index + self.chunk_size, script_length)

            self.device.push_script_chunk(script[first_index:last_index])

            progress_callback(connection_string, index, total_count)
            time.sleep(0.05)  # Wait a bit to simulate a fast transfer

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
        connection_id = self._get_connection_id(connection_string)

        if connection_id is None:
            self.send_error(operation, 'Received script chunk from unknown connection: {}'.format(connection_string))
            return

        # Check and see if we have the entire script or if we need to accumulate it
        index, count = chunk_status
        if index == 0:
            self.script = bytes()

        decoded_chunk = base64.b64decode(chunk)
        self.script += decoded_chunk

        # If there is more than one chunk and we aren't on the last one, wait until we receive them
        # all before sending them on to the device as a unit
        if index != count - 1:
            return

        error = None

        try:
            self._simulate_send_script(connection_id, self.script, self._notify_progress)

        except Exception as exc:
            self.logger.exception('Error in manager send_script')
            error = 'Internal error: {}'.format(str(exc))

        if error:
            self.send_error(operation, error, connection_string=connection_string)
        else:
            self.send_response(operation, connection_string=connection_string)

    def _notify_progress(self, connection_string, done_count, total_count):
        """Send a notification containing the current progress of the given operation. The progress is computed
        from done_count/total_count.

        Args:
            connection_string (str): The connection string of the device where the operation is in progress
            done_count (int): Number of chunks already processed
            total_count (int): Number of total chunks to proceed
        """

        self.send_notification(operations.NOTIFY_PROGRESS,
                               connection_string=connection_string,
                               done_count=done_count,
                               total_count=total_count)

    def _stream_data(self, device_uuid):
        """Stream reports to the WebSocket client in chunks

        Args:
            device_uuid (int): The uuid of the device which sent the report
        """

        connection_string = self._uuid_to_connection_string(device_uuid)

        self.streaming_data = True

        chunk = self._next_streaming_chunk(self.chunk_size)

        if len(chunk) == 0:
            self.streaming_data = False
            return

        try:
            self.send_notification(
                operations.NOTIFY_REPORT,
                connection_string=connection_string,
                payload=base64.b64encode(chunk)
            )
            self._defer(self._stream_data, [device_uuid])
        except HardwareError as err:
            self.logger.exception(err)
            self._audit('ErrorStreamingReport')

    def _send_trace(self, device_uuid):
        """Stream tracing data to the WebSocket client in chunks

        Args:
            device_uuid (int): The uuid of the device which sent the trace
        """

        connection_string = self._uuid_to_connection_string(device_uuid)

        self.tracing_data = True

        chunk = self._next_tracing_chunk(self.chunk_size)

        if len(chunk) == 0:
            self.tracing_data = False
            return

        try:
            self.send_notification(
                operations.NOTIFY_TRACE,
                connection_string=connection_string,
                payload=base64.b64encode(chunk)
            )
            self._defer(self._send_trace, [device_uuid])
        except HardwareError as err:
            self.logger.exception(err)
            self._audit('ErrorStreamingReport')

    def clean_device(self):
        """Clean up after a client disconnects

        This resets any open interfaces on the virtual device and clears any
        in progress traces and streams.
        """

        if self.rpc_enabled:
            self.device.close_rpc_interface()
            self.rpc_enabled = False

        if self.debug_enabled:
            self.device.close_debug_interface()
            self.debug_enabled = False

        if self.script_enabled:
            self.device.close_script_interface()
            self.script_enabled = False

        if self.streaming_enabled:
            self.device.close_streaming_interface()
            self.streaming_enabled = False

        if self.tracing_enabled:
            self.device.close_tracing_interface()
            self.tracing_enabled = False

        self._clear_reports()
        self._clear_traces()

    def on_client_disconnect(self, client, server):
        """Callback function called when a WebSocket client disconnects from the server.

        Args:
            client (dict): A dictionary containing client information
                id (int):
                    A unique client ID
                address (tuple):
                    Tuple containing (client IP address, client port)
                handler (WebSocketHandler):
                    An instance of the websocket handler (which is a stream to send/receive messages)

            server (WebsocketServer): The server instance
        """

        self.logger.info('Client {} disconnected'.format(client['id']))

        if self.device.connected:
            # Disconnect the virtual device
            connection_string = self._uuid_to_connection_string(self.device.iotile_id)
            self._disconnect_from_device(connection_string)

        self.client = None

    def stop(self):
        """Safely shut down this interface."""

        super(WebSocketVirtualInterface, self).stop()

        if self.device.connected:
            connection_string = self._uuid_to_connection_string(self.device.iotile_id)
            self._disconnect_from_device(connection_string)
            self.device.stop()

        if self.client is not None:
            # Send closing packet
            self.server.server_close()

        self.server.shutdown()
        self.server_thread.join()
