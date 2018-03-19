"""A VirtualInterface that provides access to a virtual IOTile device through websocket"""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import binascii
import datetime
import logging
import msgpack
import threading
import time
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.exceptions import ArgumentError, HardwareError
from websocket_server import WebsocketServer


class WebSocketVirtualInterface(VirtualIOTileInterface):
    """ Run a simple WebSocket server and provide an interface between it and a virtual device.

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

        # Set logger
        self.logger = logging.getLogger('virtual.websocket')
        self.logger.setLevel(logging.DEBUG)  # TODO: remove this line
        self.logger.addHandler(logging.NullHandler())

        # Initialize states
        # - Interfaces
        self.streaming_enabled = False
        self.tracing_enabled = False
        self.script_enabled = False
        # - Current action
        self.streaming_data = False
        self.tracing_data = False

        # WebSocket client
        self.client = None

        # WebSocket server
        self.server = WebsocketServer(port, host='localhost', loglevel=logging.DEBUG)
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

        if b'__datetime__' in obj:
            obj = datetime.datetime.strptime(obj[b'as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        """Encode a msgpack'ed datetime."""

        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%fZ").encode()}
        return obj

    def start(self, device):
        """Start serving access to this VirtualIOTileDevice

        Args:
            device (VirtualIOTileDevice): The device we will be providing access to
        """

        super(WebSocketVirtualInterface, self).start(device)

        self.server_thread.start()

    def stop(self):
        """Safely shut down this interface."""

        super(WebSocketVirtualInterface, self).stop()

        if self.device.connected:
            self._disconnect_device()

        if self.client is not None:
            # Send closing packet
            self.server.server_close()

        self.server.shutdown()
        self.server_thread.join()

    def process(self):
        """Periodic nonblocking processes."""

        super(WebSocketVirtualInterface, self).process()

        if (not self.streaming_data) and (not self.reports.empty()):
            self._stream_data()

        if (not self.tracing_data) and (not self.traces.empty()):
            self._send_trace()

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
            self._disconnect_device()

        self.client = None

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

        message = msgpack.unpackb(message, raw=False, object_hook=self.decode_datetime)

        if message['type'] == 'command':
            self.handle_command(message)
        else:
            self.send_error('Unknown type')
            self.logger.error('Received message with unknown type: {}'.format(message))

    def handle_command(self, cmd):
        """Execute the action matching the received command.

        Args:
            cmd (dict): Command information, like 'operation' name or some parameters needed to execute the action
        """

        op = cmd['operation']

        response = None
        error = None

        if op == 'scan':
            devices = self._generate_scan_response()
            response = {'devices': devices}

        elif op == 'connect':
            self._connect_device()
            response = {'connection_id': self.device.iotile_id}

        elif op == 'disconnect':
            self._disconnect_device()

        elif op == 'open_interface':
            interface = cmd['interface']
            try:
                self.open_interface(interface)
            except ArgumentError as err:
                self.logger.error('Unknown interface received: {}'.format(interface))
                error = str(err)

        elif op == 'send_rpc':
            try:
                status, return_value = self._call_rpc(cmd['address'], cmd['rpc_id'], cmd['payload'])
                response = {'return_value': return_value, 'status': status}
            except Exception as err:
                self.logger.error('Error while sending RPC: {}'.format(err))
                error = str(err)

        elif op == 'send_script':
            try:
                index = cmd['fragment_index']
                count = cmd['fragment_count']
                connection_id = cmd['connection_id']

                self._send_script(cmd['script'])

                # Sending progress notification
                if index < count - 1:
                    self.send_progress('send_script', {
                        'connection_id': connection_id,
                        'done_count': index,
                        'total_count': count
                    })
                    return
            except Exception as err:
                self.logger.error('Error while sending script: {}'.format(err))
                error = str(err)

        else:
            error = 'Command {} not supported'.format(op)
            self.logger.error('Received command not supported: {}'.format(op))

        if not cmd['no_response']:
            if error is not None:
                self.send_error(error)
            else:
                self.send_response(response)

    def _call_rpc(self, address, rpc_id, payload):
        """Call an RPC on the virtual device by its address and ID.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            status (int): The status code
            return_value: response payload from the RPC
        """

        try:
            return_value = self.device.call_rpc(address, rpc_id, payload)
            status = (1 << 7)  # RPC executed with success
            if len(return_value) > 0:
                status |= (1 << 6)  # RPC returned data that should be read

        except (RPCInvalidIDError, RPCNotFoundError):
            status = (1 << 1)  # Indicates RPC address or id not correct
            return_value = ''
        except TileNotFoundError:
            status = 0xFF  # Indicates RPC had an error
            return_value = ''

        self._audit("RPCReceived",
                    rpc_id=rpc_id,
                    address=address,
                    payload=binascii.hexlify(payload),
                    status=status,
                    response=binascii.hexlify(return_value))

        return status, return_value

    def _generate_scan_response(self):
        """Return a dict containing the virtual device information to send a scan response."""

        return [
            {
                'connection_string': self.device.iotile_id,
                'pending_data': self.device.pending_data,
                'name': self.device.name,
                'connected': self.device.connected,
                'uuid': self.device.iotile_id
            }
        ]

    def open_interface(self, interface):
        """Open a given interface on the virtual device.
        Args:
            interface (str): name of the interface

        Raises:
            ArgumentError: If interface not found
        """

        if interface == 'rpc':
            self.device.open_rpc_interface()
            self._audit('RPCInterfaceOpened')

        elif interface == 'streaming':
            if self.streaming_enabled:
                self.streaming_enabled = False
                self.device.close_streaming_interface()
                self._audit('StreamingInterfaceClosed')
            else:
                self.streaming_enabled = True
                reports = self.device.open_streaming_interface()
                if reports is not None:
                    self._queue_reports(*reports)
                self._audit('StreamingInterfaceOpened')

        elif interface == 'tracing':
            if self.tracing_enabled:
                self.tracing_enabled = False
                self.device.close_tracing_interface()
                self._audit('TracingInterfaceClosed')
            else:
                self.tracing_enabled = True
                traces = self.device.open_tracing_interface()
                if traces is not None:
                    self._queue_traces(*traces)
                self._audit('TracingInterfaceOpened')

        elif interface == 'script':
            if self.script_enabled:
                self.script_enabled = False
                self.device.close_script_interface()
                self._audit('ScriptInterfaceClosed')
            else:
                self.script_enabled = True
                self.device.open_script_interface()
                self._audit('ScriptInterfaceOpened')

        else:
            raise ArgumentError('Unknown interface')

    def send_response(self, payload=None):
        """Send a command response indicating it has been executed with success.
        Args:
            payload (dict): data to send with the response
        """

        response = {'type': 'response', 'success': True}
        if payload is not None:
            response['payload'] = payload

        self.logger.debug('Sending response: {}'.format(response))
        self._send_message(response)

    def send_report(self, payload=None):
        """Send a report chunk.
        Args:
            payload (bytes): data to send with the report chunk

        Raises:
            ArgumentError: If payload is empty
        """

        if payload is None:
            raise ArgumentError("Can't send empty report")

        report = {'type': 'report', 'payload': payload}

        self.logger.debug('Sending report: {}'.format(report))
        self._send_message(report)

    def send_trace(self, payload=None):
        """Send a trace chunk.
        Args:
            payload (bytes): data to send with the trace chunk

        Raises:
            ArgumentError: If payload is empty
        """

        if payload is None:
            raise ArgumentError("Can't send empty trace")

        trace = {'type': 'trace', 'payload': payload}

        self.logger.debug('Sending trace: {}'.format(trace))
        self._send_message(trace)

    def send_progress(self, operation, payload=None):
        """Send a progress notification (used when uploading script for example).

        Args:
            operation (str): name of the operation currently in progress
            payload (dict): data to send with the notification

        Raises:
            ArgumentError: If payload is empty
        """

        if payload is None:
            raise ArgumentError("Can't send empty report")

        progress = {'type': 'notification', 'operation': operation, 'payload': payload}

        self.logger.debug('Sending progress: {}'.format(progress))
        self._send_message(progress)

    def send_error(self, reason):
        """Send an error message containing the failure reason
        Args:
            reason (str): the failure reason
        """

        error = {'type': 'response', 'success': False, 'reason': reason}

        self.logger.debug('Sending error: {}'.format(error))
        self._send_message(error)

    def _send_message(self, payload):
        """Send a binary message to the WebSocket connected client, after having msgpack'ed it

        Args:
            payload (dict): data to send
        """

        try:
            message = msgpack.packb(payload, default=self.encode_datetime)
            self.server.send_message(self.client, message, binary=True)
        except Exception as err:
            self.logger.exception(err)

    def _connect_device(self):
        """Connect to the virtual device."""

        self.device.connected = True
        self._audit('ClientConnected')

    def _disconnect_device(self):
        """Disconnect from the virtual device after cleaning it."""

        self.clean_device()
        self.device.connected = False
        self._audit('ClientDisconnected')

    def clean_device(self):
        """Clean up after a client disconnects

        This resets any open interfaces on the virtual device and clears any
        in progress traces and streams.
        """

        if self.streaming_enabled:
            self.device.close_streaming_interface()
            self.streaming_enabled = False

        if self.tracing_enabled:
            self.device.close_tracing_interface()
            self.tracing_enabled = False

        self._clear_reports()
        self._clear_traces()

    def _stream_data(self, chunk=None):
        """Stream reports to the WebSocket client in 20 byte chunks

        Args:
            chunk (bytes): A chunk that should be sent instead of requesting a
                new chunk from the pending reports.
        """

        self.streaming_data = True

        if chunk is None:
            chunk = self._next_streaming_chunk(20)

        if chunk is None or len(chunk) == 0:
            self.streaming_data = False
            return

        try:
            self.send_report(chunk)
            self._defer(self._stream_data)
        except HardwareError as err:
            return_value = err.params['return_value']

            # If we're told we ran out of memory, wait and try again
            if return_value.get('code', 0) == 0x182:
                time.sleep(.02)
                self._defer(self._stream_data, [chunk])
            elif return_value.get('code', 0) == 0x181:  # Invalid state, the other side likely disconnected midstream
                self._audit('ErrorStreamingReport')
            else:
                self.logger.exception(err)
                self._audit('ErrorStreamingReport')

    def _send_trace(self, chunk=None):
        """Stream tracing data to the WebSocket client in 20 byte chunks

        Args:
            chunk (bytes): A chunk that should be sent instead of requesting a
                new chunk from the pending reports.
        """

        self.tracing_data = True

        if chunk is None:
            chunk = self._next_tracing_chunk(20)

        if chunk is None or len(chunk) == 0:
            self.tracing_data = False
            return

        try:
            self.send_trace(chunk)
            self._defer(self._send_trace)
        except HardwareError as err:
            return_value = err.params['return_value']

            # If we're told we ran out of memory, wait and try again
            if return_value.get('code', 0) == 0x182:
                time.sleep(.02)
                self._defer(self._send_trace, [chunk])
            elif return_value.get('code', 0) == 0x181:  # Invalid state, the other side likely disconnected midstream
                self._audit('ErrorStreamingReport')
            else:
                self.logger.exception(err)
                self._audit('ErrorStreamingReport')

    def _send_script(self, chunk):
        """Send a script to the connected device.

        Args:
            chunk (bytes): The binary script to send to the device
        """

        self.device.push_script_chunk(chunk)

#LUNDI:
    # TODO: faire messages.py pour verifier commandes (cf awsiot) : pour virtual_websocket ET device_adapter

# => PR

# TODO: faire nouveau WebSocketHandler2 pour de vrai
# TODO: ecrire tests

# TODO: convertir fonctions device_adapter.py en async -> voir avec Tim parce que contraire au ValidatingWSClient
# TODO: faire progress_callback pour script (quand async) + tester script -> voir avec Tim
