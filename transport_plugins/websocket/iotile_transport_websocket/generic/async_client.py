import logging
import uuid
import inspect
import asyncio
import websockets
from iotile.core.exceptions import ExternalError, ValidationError
from iotile.core.utilities.async_tools import OperationManager, SharedLoop
from iotile.core.utilities.schema_verify import Verifier
from .packing import pack, unpack
from .messages import VALID_SERVER_MESSAGE


class AsyncValidatingWSClient:
    """An asynchronous websocket client that validates messages received.

    This client is designed to allow the easy construction of client/server
    protocols where the client can send commands to the server that
    receive responses and the server can push events to the client at
    any time.

    The schema of all messages exchanged are validated according to
    SchemaVerifiers to ensure they are correct before passing on to
    the underlying handlers.

    Messages are packed using msgpack in a binary format and are decoded and
    validated automatically.

    Args:
        url (str): The URL of the websocket server that we should connect to.
        loop (BackgroundEventLoop): The background event loop that we should
            run in, or None to use the default shared background loop.
        logger_name (str): Optional name for the logger we should use to
            log messages.
    """

    DISCONNECT_EVENT = "__internal_ws_disconnect_event"

    def __init__(self, url, loop=SharedLoop, logger_name=__name__):
        self.url = url

        self._con = None
        self._connection_task = None
        self._logger = logging.getLogger(logger_name)
        self._loop = loop
        self._event_validators = {}
        self._allowed_exceptions = {}
        self._manager = OperationManager(loop=loop)

        logger = logging.getLogger('websockets')
        logger.setLevel(logging.ERROR)
        logger.addHandler(logging.NullHandler())

    def allow_exception(self, exc_class):
        """Allow raising this class of exceptions from commands.

        When a command fails on the server side due to an exception, by
        default it is turned into a string and raised on the client side as an
        ExternalError.  The original class name is sent but ignored.  If you
        would like to instead raise an instance of the same exception on the
        client side, you can pass the exception class object to this method
        and instances of that exception will be reraised.

        The caveat is that the exception must be creatable with a single
        string parameter and it should have a ``msg`` property.

        Args:
            exc_class (class): A class object with the exception that
                we should allow to pass from server to client.
        """

        name = exc_class.__name__
        self._allowed_exceptions[name] = exc_class

    async def start(self, name="websocket_client"):
        """Connect to the websocket server.

        This method will spawn a background task in the designated event loop
        that will run until stop() is called.  You can control the name of the
        background task for debugging purposes using the name parameter.  The
        name is not used in anyway except for debug logging statements.

        Args:
            name (str): Optional name for the background task.
        """

        self._con = await websockets.connect(self.url)
        self._connection_task = self._loop.add_task(self._manage_connection(), name=name)

    async def stop(self):
        """Stop this websocket client and disconnect from the server.

        This method is idempotent and may be called multiple times.  If called
        when there is no active connection, it will simply return.
        """

        if self._connection_task is None:
            return

        try:
            await self._connection_task.stop()
        finally:
            self._con = None
            self._connection_task = None
            self._manager.clear()

    async def send_command(self, command, args, validator, timeout=10.0):
        """Send a command and synchronously wait for a single response.

        Args:
            command (string): The command name
            args (dict): Optional arguments.
            validator (Verifier): A SchemaVerifier to verify the response
                payload.
            timeout (float): The maximum time to wait for a response.
                Defaults to 10 seconds.

        Returns:
            dict: The response payload

        Raises:
            ExternalError: If the server is not connected or the command
                fails.
            asyncio.TimeoutError: If the command times out.
            ValidationError: If the response payload does not match the
                given validator.
        """

        if self._con is None:
            raise ExternalError("No websock connection established")

        cmd_uuid = str(uuid.uuid4())
        msg = dict(type='command', operation=command, uuid=cmd_uuid,
                   payload=args)

        packed = pack(msg)

        # Note: register future before sending to avoid race conditions
        response_future = self._manager.wait_for(type="response", uuid=cmd_uuid,
                                                 timeout=timeout)

        await self._con.send(packed)

        response = await response_future

        if response.get('success') is False:
            self._raise_error(command, response)

        if validator is None:
            return response.get('payload')

        return validator.verify(response.get('payload'))

    def _raise_error(self, command, response):
        exc_name = response.get('exception_class')
        reason = response.get('reason')

        exc_class = self._allowed_exceptions.get(exc_name)
        if exc_class is not None:
            raise exc_class(reason)

        raise ExternalError("Command {} failed".format(command),
                            reason=response.get('reason'))

    async def _manage_connection(self):
        """Internal coroutine for managing the client connection."""

        try:
            while True:
                message = await self._con.recv()

                try:
                    unpacked = unpack(message)
                except Exception:  # pylint:disable=broad-except;This is a background worker
                    self._logger.exception("Corrupt message received")
                    continue

                if not VALID_SERVER_MESSAGE.matches(unpacked):
                    self._logger.warning("Dropping invalid message from server: %s", unpacked)
                    continue

                # Don't block until all callbacks have finished since once of
                # those callbacks may call self.send_command, which would deadlock
                # since it couldn't get the response until it had already finished.
                if not await self._manager.process_message(unpacked, wait=False):
                    self._logger.warning("No handler found for received message, message=%s", unpacked)
        except asyncio.CancelledError:
            self._logger.info("Closing connection to server due to stop()")
        finally:
            await self._manager.process_message(dict(type='event', name=self.DISCONNECT_EVENT, payload=None))
            await self._con.close()

    def register_event(self, name, callback, validator):
        """Register a callback to receive events.

        Every event with the matching name will have its payload validated
        using validator and then will be passed to callback if validation
        succeeds.

        Callback must be a normal callback function, coroutines are not
        allowed.  If you need to run a coroutine you are free to schedule it
        from your callback.

        Args:
            name (str): The name of the event that we are listening
                for
            callback (callable): The function that should be called
                when a message that matches validator is received.
            validator (Verifier): A schema verifier that will
                validate a received message uniquely
        """

        async def _validate_and_call(message):
            payload = message.get('payload')

            try:
                payload = validator.verify(payload)
            except ValidationError:
                self._logger.warning("Dropping invalid payload for event %s, payload=%s",
                                     name, payload)
                return

            try:
                result = callback(payload)
                if inspect.isawaitable(result):
                    await result
            except:  # pylint:disable=bare-except;This is a background logging routine
                self._logger.error("Error calling callback for event %s, payload=%s",
                                   name, payload, exc_info=True)

        self._manager.every_match(_validate_and_call, type="event", name=name)

    def post_command(self, command, args):
        """Post a command asynchronously and don't wait for a response.

        There is no notification of any error that could happen during
        command execution.  A log message will be generated if an error
        occurred.  The command's response is discarded.

        This method is thread-safe and may be called from inside or ouside
        of the background event loop.  If there is no websockets connection,
        no error will be raised (though an error will be logged).

        Args:
            command (string): The command name
            args (dict): Optional arguments
        """

        self._loop.log_coroutine(self.send_command(command, args, Verifier()))
