"""A server implementation matching AsyncValidatingWSClient."""

import logging
import asyncio
import websockets

from iotile.core.exceptions import ValidationError

from .messages import VALID_CLIENT_MESSAGE
from .packing import pack, unpack
from .errors import ServerCommandError
from iotile.core.utilities.async_tools import SharedLoop


class _ConnectionContext:
    def __init__(self, server, con):
        self.server = server
        self.connection = con
        self.operations = set()
        self.user_data = None


class AsyncValidatingWSServer:
    """A websocket server supporting command/response and server push.

    There is only one kind of message that can be sent from client to server:
    COMMAND.  Those messages are dispatched to command handler tasks that run
    in parallel as coroutines and send a RESPONSE message back when they are
    finished.

    The server can also, at any time, send an EVENT message to the client,
    which is able to register a callback for the event.

    This class is the server side implementation of AsyncValidatingWSClient
    and is designed to be used with that class.

    Args:
        host (str): The host name on which we should register this server
        port (int): The port we should use.  If None is given (the default),
            then a random port is chosen and will be accessible on the
            port property after ``await start()`` finished without error.
        loop (BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    OPERATIONS_MAX_PRUNE = 10

    def __init__(self, host, port=None, loop=SharedLoop):
        self.task = None
        self.host = host
        self.port = port

        self._commands = {}
        self._server_task = None
        self._loop = loop
        self._logger = logging.getLogger(__name__)

        logger = logging.getLogger('websockets')
        logger.setLevel(logging.ERROR)
        logger.addHandler(logging.NullHandler())

    async def prepare_conn(self, _con):
        """Called when a new connection is established.

        This method is designed to allow subclasses to store, per connection
        state.  The return value will be saved in a per connection context
        that is passed to all command coroutines.

        Args:
            con (websockets.Connection): The connection that we are supposed
                to prepare.

        Returns:
            object: Any user data that needs to be tracked with this connection.
        """

        return None

    async def teardown_conn(self, context):
        """Called when a connection is finalized.

        This is the partner call to prepare_conn() and is intended to give
        subclasses the ability to cleanly release any resources that were
        allocated along with this connection, outside of
        AsyncValidatingWSServer.

        Args:
            context (_ConnectionContext): An object with all of the
                associated data about the connection including any
                user data returned by prepare_conn().
        """

        pass

    def register_command(self, name, handler, validator):
        """Register a coroutine command handler.

        This handler will be called whenever a command message is received
        from the client, whose operation key matches ``name``.  The handler
        will be called as::

            response_payload = await handler(cmd_payload, context)

        If the coroutine returns, it will be assumed to have completed
        correctly and its return value will be sent as the result of the
        command.  If the coroutine wishes to signal an error handling the
        command, it must raise a ServerCommandError exception that contains a
        string reason code for the error.  This will generate an error
        response to the command.

        The cmd_payload is first verified using the SchemaVerifier passed in
        ``validator`` and handler is only called if verification succeeds. If
        verification fails, a failure response to the command is returned
        automatically to the client.

        Args:
            name (str): The unique command name that will be used to dispatch
                client command messages to this handler.
            handler (coroutine function): A coroutine function that will be
                called whenever this command is received.
            validator (SchemaVerifier): A validator object for checking the
                command payload before calling this handler.
        """

        self._commands[name] = (handler, validator)

    async def start(self):
        """Start the websocket server.

        When this method returns, the websocket server will be running and
        the port property of this class will have its assigned port number.

        This method should be called only once in the lifetime of the server
        and must be paired with a call to stop() to cleanly release the
        server's resources.
        """

        if self._server_task is not None:
            self._logger.debug("AsyncValidatingWSServer.start() called twice, ignoring")
            return

        started_signal = self._loop.create_future()
        self._server_task = self._loop.add_task(self._run_server_task(started_signal))

        await started_signal

        if self.port is None:
            self.port = started_signal.result()

    async def _run_server_task(self, started_signal):
        """Create a BackgroundTask to manage the server.

        This allows subclasess to attach their server related tasks as
        subtasks that are properly cleaned up when this parent task is
        stopped and not require them all to overload start() and stop()
        to perform this action.
        """

        try:
            server = await websockets.serve(self._manage_connection, self.host, self.port)
            port = server.sockets[0].getsockname()[1]
            started_signal.set_result(port)
        except Exception as err:
            self._logger.exception("Error starting server on host %s, port %s", self.host, self.port)
            started_signal.set_exception(err)
            return

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self._logger.info("Stopping server due to stop() command")
        finally:
            server.close()
            await server.wait_closed()

        self._logger.debug("Server stopped, exiting task")

    async def stop(self):
        """Stop the websocket server.

        This method will shutdown the websocket server and free all resources
        associated with it.  If there are ongoing connections at the time of
        shutdown, they will be cleanly closed.
        """

        if self._server_task is not None:
            await self._server_task.stop()
            self._server_task = None

    async def send_event(self, con, name, payload):
        """Send an event to a client connection.

        This method will push an event message to the client with the given
        name and payload.  You need to have access to the the ``connection``
        object for the client, which is only available once the client has
        connected and passed to self.prepare_conn(connection).

        Args:
            con (websockets.Connection): The connection to use to send
                the event.
            name (str): The name of the event to send.
            payload (object): The msgpack-serializable object so send
                as the event's payload.
        """

        message = dict(type="event", name=name, payload=payload)
        encoded = pack(message)
        await con.send(encoded)

    async def _manage_connection(self, con, _path):
        context = _ConnectionContext(self, con)

        try:
            try:
                context.user_data = await self.prepare_conn(con)
            except:
                self._logger.exception("Error preparing connection")
                raise

            while True:
                encoded = await con.recv()

                message = unpack(encoded)
                if not VALID_CLIENT_MESSAGE.matches(message):
                    self._logger.warning("Received invalid message %s", message)
                    continue

                handler = self._loop.get_loop().create_task(self._dispatch_message(con, message, context))
                context.operations.add(handler)

                if len(context.operations) > self.OPERATIONS_MAX_PRUNE:
                    _prune_finished(context.operations)
        except websockets.exceptions.ConnectionClosed:
            self._logger.info("Connection closed")
        finally:
            await _cancel_operations(context.operations)

            try:
                await self.teardown_conn(context)
            except:  #pylint:disable=bare-except;This is a background worker
                self._logger.exception("Error tearing down connecion")

    async def _dispatch_message(self, con, message, context):
        cmd = message.get('operation')
        cmd_uuid = message.get('uuid')

        try:
            response = await self._try_call_command(message, context)
        except ServerCommandError as err:
            response = _error_response(err.reason, cmd_uuid)
        except NotImplementedError:
            self._logger.error("Command %s was not implemented", cmd)
            response = _error_response("Command %s was not implemented" % cmd, cmd_uuid)
        except Exception as err:  #pylint:disable=broad-except;We can't let a failing command take down the server
            self._logger.exception("Exception executing handler for command %s", cmd)

            if hasattr(err, 'reason'):
                reason = err.reason  #pylint:disable=no-member;We are explicitly checking for the member's existence
            elif hasattr(err, 'msg'):
                reason = err.msg  #pylint:disable=no-member;We are explicitly checking for the member's existence
            else:
                reason = str(err)

            response = _error_response(reason, cmd_uuid, exc=type(err).__name__)

        try:
            encoded_resp = pack(response)
        except:
            self._logger.exception("Unable to pack response message: %s", response)
            response = _error_response("Unable to pack response message", cmd_uuid)
            encoded_resp = pack(response)

        self._logger.debug("Sending response: %s", response)

        try:
            await con.send(encoded_resp)
        except websockets.exceptions.ConnectionClosed:
            self._logger.debug("Response %s not sent because connection closed", response)

    async def _try_call_command(self, message, context):
        name = message.get('operation')
        uuid = message.get('uuid')
        payload = message.get('payload')

        self._logger.debug("Received command %s", message)

        handler_info = self._commands.get(name)
        if handler_info is None:
            raise ServerCommandError(name, 'Command %s not found' % name)

        handler, validator = handler_info

        try:
            payload = validator.verify(payload)
        except ValidationError as err:
            raise ServerCommandError(name, 'Invalid payload: %s' % err.params.get('reason'))

        payload = await handler(payload, context)
        return dict(type="response", uuid=uuid, success=True, payload=payload)


def _error_response(reason, uuid, exc=None):
    return dict(type="response", uuid=uuid, success=False,
                reason=reason, exception_class=exc)


def _prune_finished(operations):
    to_remove = [x for x in operations if x.done()]

    for operation in to_remove:
        operations.remove(operation)


async def _cancel_operations(operations):
    for handler in operations:
        if not handler.done():
            handler.cancel()

    await asyncio.gather(*list(operations), return_exceptions=True)
