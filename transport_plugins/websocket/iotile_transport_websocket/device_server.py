"""Generic implementation of serving access to a device over websockets."""

import logging
import base64
import websockets
from iotile.core.utilities import SharedLoop
from iotile.core.hw.transport.server import StandardDeviceServer
from iotile.core.hw.exceptions import VALID_RPC_EXCEPTIONS, DeviceServerError, DeviceAdapterError
from iotile.core.hw.virtual import pack_rpc_response
from .generic import AsyncValidatingWSServer, ServerCommandError
from .protocol import COMMANDS, OPERATIONS

_MISSING = object()

class WebSocketDeviceServer(StandardDeviceServer):
    """A device server for connections to multiple devices over websockets.

    This class connects to an AbstractDeviceAdapter and serves it over
    Websockets. Currently the support arguments to pass in args are:

    - ``host``: The host name to serve on, defaults to 127.0.0.1
    - ``port``: The port name to serve on, defaults to a random port if not specified.
      If a random port is used, its value can be read on the ``port`` property after
      start() has completed.

    Args:
        adapter (AbstractDeviceAdapter): The device adapter that we should use
            to find devices.
        args (dict): Arguments to this device server.
        loop (BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, adapter, args=None, *, loop=SharedLoop):
        host = args.get('host', '127.0.0.1')
        port = args.get('port', None)

        StandardDeviceServer.__init__(self, adapter, args, loop=loop)

        self.port = None
        self.server = AsyncValidatingWSServer(host, port, loop=loop)
        self.chunk_size = 4*1024  # Config chunk size to be 4kb for traces and reports streaming
        self._logger = logging.getLogger(__name__)

        self.server.register_command(OPERATIONS.CONNECT, self.connect_message, COMMANDS.ConnectCommand)
        self.server.register_command(OPERATIONS.PROBE, self.probe_message, COMMANDS.ProbeCommand)
        self.server.register_command(OPERATIONS.DISCONNECT, self.disconnect_message, COMMANDS.DisconnectCommand)
        self.server.register_command(OPERATIONS.OPEN_INTERFACE, self.open_interface_message, COMMANDS.OpenInterfaceCommand)
        self.server.register_command(OPERATIONS.CLOSE_INTERFACE, self.close_interface_message, COMMANDS.CloseInterfaceCommand)
        self.server.register_command(OPERATIONS.SEND_RPC, self.send_rpc_message, COMMANDS.SendRPCCommand)
        self.server.register_command(OPERATIONS.SEND_SCRIPT, self.send_script_message, COMMANDS.SendScriptCommand)
        self.server.register_command(OPERATIONS.DEBUG, self.debug_command_message, COMMANDS.SendDebugCommand)

        # Setup our hooks whenever a client connects or disconnects
        self.server.prepare_conn = self.prepare_conn
        self.server.teardown_conn = self.teardown_conn

    async def prepare_conn(self, conn):
        client_id = self.setup_client(user_data=conn, broadcast=True)

        self._logger.info("New client connection: %s", client_id)
        return client_id

    async def teardown_conn(self, context):
        client_id = context.user_data

        self._logger.info("Tearing down client connection: %s", client_id)
        await self.teardown_client(client_id)

    async def start(self):
        """Start serving access to devices.

        This method must not return until the devices are accessible over the
        implementations chosen server protocol.  It must be possible to
        immediately attach an AbstractDevice adapter to this server and use it
        without any race conditions.

        For example, if the server is configured to use a TCP port to serve
        devices, the TCP port must be bound and listening for connections when
        this coroutine returns.
        """

        await self.server.start()
        self.port = self.server.port

    async def stop(self):
        """Stop serving access to devices.

        Subclass **must not** return until the devices are no longer accessible
        over the implementation's chosen server protocol.  There should be no
        race condition where a client is still able to invoke a function on
        this server after stop has returned.  This is important because server
        container running this AbstractDeviceServer may no longer be in a
        state to respond allow for client connections safely.

        Subclasses **must** cleanly disconnect from any devices accessed via
        ``adapter`` before stopping.  It is the job of the ``AbstractDeviceServer``
        to release all of its internal resources.  It is not the job of ``adapter``
        to somehow know that a particular DeviceServer has stopped and free the
        resources associated with that server.

        Subclasses **should** cleanly disconnect any clients when stopped if
        possible, rather than just breaking all sockets, for example.
        """

        await self.server.stop()

        # Cleanup any resources we had on the adapter
        await super(WebSocketDeviceServer, self).stop()

    async def probe_message(self, _message, context):
        """Handle a probe message.

        See :meth:`AbstractDeviceAdapter.probe`.
        """
        client_id = context.user_data

        await self.probe(client_id)

    async def connect_message(self, message, context):
        """Handle a connect message.

        See :meth:`AbstractDeviceAdapter.connect`.
        """
        conn_string = message.get('connection_string')
        client_id = context.user_data

        await self.connect(client_id, conn_string)

    async def disconnect_message(self, message, context):
        """Handle a disconnect message.

        See :meth:`AbstractDeviceAdapter.disconnect`.
        """

        conn_string = message.get('connection_string')
        client_id = context.user_data

        await self.disconnect(client_id, conn_string)

    async def open_interface_message(self, message, context):
        """Handle an open_interface message.

        See :meth:`AbstractDeviceAdapter.open_interface`.
        """

        conn_string = message.get('connection_string')
        interface = message.get('interface')
        client_id = context.user_data

        await self.open_interface(client_id, conn_string, interface)

    async def close_interface_message(self, message, context):
        """Handle a close_interface message.

        See :meth:`AbstractDeviceAdapter.close_interface`.
        """

        conn_string = message.get('connection_string')
        interface = message.get('interface')
        client_id = context.user_data

        await self.close_interface(client_id, conn_string, interface)

    async def send_rpc_message(self, message, context):
        """Handle a send_rpc message.

        See :meth:`AbstractDeviceAdapter.send_rpc`.
        """

        conn_string = message.get('connection_string')
        rpc_id = message.get('rpc_id')
        address = message.get('address')
        timeout = message.get('timeout')
        payload = message.get('payload')
        client_id = context.user_data

        self._logger.debug("Calling RPC %d:0x%04X with payload %s on %s",
                           address, rpc_id, payload, conn_string)

        response = bytes()
        err = None
        try:
            response = await self.send_rpc(client_id, conn_string, address, rpc_id, payload, timeout=timeout)
        except VALID_RPC_EXCEPTIONS as internal_err:
            err = internal_err
        except (DeviceAdapterError, DeviceServerError):
            raise
        except Exception as internal_err:
            self._logger.warning("Unexpected exception calling RPC %d:0x%04x", address, rpc_id, exc_info=True)
            raise ServerCommandError('send_rpc', str(internal_err)) from internal_err

        status, response = pack_rpc_response(response, err)
        return {
            'status': status,
            'payload': base64.b64encode(response)
        }

    async def send_script_message(self, message, context):
        """Handle a send_script message.

        See :meth:`AbstractDeviceAdapter.send_script`.
        """

        script = message.get('script')
        conn_string = message.get('connection_string')
        client_id = context.user_data

        if message.get('fragment_count') != 1:
            raise DeviceServerError(client_id, conn_string, 'send_script', 'fragmented scripts are not yet supported')

        await self.send_script(client_id, conn_string, script)

    async def debug_command_message(self, message, context):
        """Handle a debug message.

        See :meth:`AbstractDeviceAdapter.debug`.
        """

        conn_string = message.get('connection_string')
        command = message.get('command')
        args = message.get('args')
        client_id = context.user_data

        result = await self.debug(client_id, conn_string, command, args)
        return result

    async def client_event_handler(self, client_id, event_tuple, user_data):
        """Forward an event on behalf of a client.

        This method is called by StandardDeviceServer when it has an event that
        should be sent to a client.

        Args:
            client_id (str): The client that we should send this event to
            event_tuple (tuple): The conn_string, event_name and event
                object passed from the call to notify_event.
            user_data (object): The user data passed in the call to
                :meth:`setup_client`.
        """

        #TODO: Support sending disconnection events

        conn_string, event_name, event = event_tuple

        if event_name == 'report':
            report = event.serialize()
            report['encoded_report'] = base64.b64encode(report['encoded_report'])
            msg_payload = dict(connection_string=conn_string, serialized_report=report)
            msg_name = OPERATIONS.NOTIFY_REPORT
        elif event_name == 'trace':
            encoded_payload = base64.b64encode(event)
            msg_payload = dict(connection_string=conn_string, payload=encoded_payload)
            msg_name = OPERATIONS.NOTIFY_TRACE
        elif event_name == 'progress':
            msg_payload = dict(connection_string=conn_string, operation=event.get('operation'),
                               done_count=event.get('finished'), total_count=event.get('total'))
            msg_name = OPERATIONS.NOTIFY_PROGRESS
        elif event_name == 'device_seen':
            msg_payload = event
            msg_name = OPERATIONS.NOTIFY_DEVICE_FOUND
        elif event_name == 'broadcast':
            report = event.serialize()
            report['encoded_report'] = base64.b64encode(report['encoded_report'])
            msg_payload = dict(connection_string=conn_string, serialized_report=report)
            msg_name = OPERATIONS.NOTIFY_BROADCAST
        else:
            self._logger.debug("Not forwarding unknown event over websockets: %s", event_tuple)
            return

        try:
            self._logger.debug("Sending event %s: %s", msg_name, msg_payload)
            await self.server.send_event(user_data, msg_name, msg_payload)
        except websockets.exceptions.ConnectionClosed:
            self._logger.debug("Could not send notification because connection was closed for client %s", client_id)
