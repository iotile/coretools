"""A websocket client that validates messages received and dispatches them."""

import asyncio
import websockets

import msgpack
import datetime
import logging
import uuid
from iotile.core.exceptions import IOTileException, InternalError, ValidationError, TimeoutExpiredError
from iotile.core.utilities.schema_verify import Verifier, DictionaryVerifier, \
    StringVerifier, LiteralVerifier, OptionsVerifier

from iotile.core.utilities.event_loop import EventLoop
# The prescribed schema of command response messages
# Messages with this format are automatically processed inside the ValidatingWSClient
SuccessfulResponseSchema = DictionaryVerifier()
SuccessfulResponseSchema.add_required('type', LiteralVerifier('response'))
SuccessfulResponseSchema.add_required('success', LiteralVerifier(True))
SuccessfulResponseSchema.add_optional('payload', Verifier())

FailureResponseSchema = DictionaryVerifier()
FailureResponseSchema.add_required('type', LiteralVerifier('response'))
FailureResponseSchema.add_required('success', LiteralVerifier(False))
FailureResponseSchema.add_required('reason', StringVerifier())

ResponseSchema = OptionsVerifier(SuccessfulResponseSchema, FailureResponseSchema)


class ValidatingWSClient:
    """An asynchronous websocket client that validates messages received.

    Messages are assumed to be packed using msgpack in a binary format
    and are decoded and validated against message type schema.  Matching
    messages are dispatched to the appropriate handler and messages that
    match no attached schema are logged and dropped.
    """

    def __init__(self, url, logger_name=__name__):
        """Constructor.

        Args:
        url (string): The URL of the websocket server that we want
            to connect to.
        logger_name (string): An optional name that errors are logged to
        """
        self.con = None
        self.url = url
        self.loop = EventLoop.get_loop()
        self._logger = logging.getLogger(logger_name)
        self.validators = [(ResponseSchema, self._on_response_received)]
        self.command_lock = asyncio.Lock(loop=self.loop)
        self.response_queue = asyncio.Queue(1, loop=self.loop)

        asyncio.ensure_future(self.connection_object(), loop=self.loop)
        asyncio.ensure_future(self.handle_message(), loop=self.loop)

    async def connection_object(self):
        """Async object that contains the websocket connection (and keeps it open for us)"""
        self.con = await websockets.connect(self.url)

    async def send_command(self, command, args, timeout=10.0):
        """Send a command and synchronously wait for a single response.

        Args:
            command (string): The command name
            args (dict): Optional arguments
            timeout (float): The maximum time to wait for a response
        """
        while not self.con:
            await asyncio.sleep(1)
        msg = {x: y for x, y in args.items()}
        msg['type'] = 'command'
        msg['operation'] = command
        msg['no_response'] = False
        packed = msgpack.packb(msg, use_bin_type=True)
        async with self.command_lock:
            await self.con.send(packed)
            try:
                results = await asyncio.wait_for(self.response_queue.get(), timeout=timeout, loop=self.loop)
            except asyncio.TimeoutError:
                results = {'success': False, 'reason': 'timeout'}
            return results

    async def handle_message(self):
        """Listener for when a message is received from the ws server.

        (This replaces the message_received callback from the threaded version)

        The message must be encoded using message_pack
        """

        while not self.con:
            await asyncio.sleep(1)

        try:
            while True:
                message = await self.con.recv()
                try:
                    unpacked = self._unpack(message)
                except Exception as exc:
                    self._logger.error("Corrupt message received, parse exception = %s", str(exc))
                    continue
                # We need to delegate the callback to a processor to keep our callback exceptions
                # Without blocking the websocket message handler with an await
                # There may still be a deadlock lurking in here somewhere, but it should be fine...
                asyncio.ensure_future(self.process_message(unpacked), loop=self.loop)
        finally:
            await self.con.close()

    async def process_message(self, unpacked):
        """Process a message asynchronously from the websocket message handler"""

        handler_found = False
        # We have to break instead of return to keep the coroutine alive
        for validator, callback in self.validators:
            # Look for the first callback that can handle this message
            # if no one can handle it, log an error and discard the message.
            try:
                validator.verify(unpacked)
            except ValidationError:
                continue
            try:
                await callback(unpacked)
                handler_found = True
            except IOTileException as exc:
                self._logger.error("Exception handling websocket message, exception = %s", str(exc))
                break
            except Exception as exc:
                self._logger.error("Non-IOTile exception handling websocket message, exception = %s", str(exc))
                break
        if not handler_found:
            self._logger.warn("No handler found for received message, message=%s", str(unpacked))

    def add_message_type(self, validator, callback):
        """Add a message type that should trigger a callback.

        Each validator must be unique, in that a message will
        be dispatched to the first callback whose validator
        matches the message.

        Args:
            validator (Verifier): A schema verifier that will
                validate a received message uniquely
            callback (callable): The function that should be called
                when a message that matches validator is received.
        """

        self.validators.append((validator, callback))

    async def send_ping(self, timeout=10.0):
        """Send a ping message to keep connection alive and to verify
        if the server is still there
        """

        await self.con.ping(self.control_data, timeout=timeout)
        await self.con.pong()

    async def post_command(self, command, args):
        """Post a command asynchronously and don't wait for a response.

        Args:
            command (string): The command name
            args (dict): Optional arguments
        """
        while not self.con:
            await asyncio.sleep(1)

        msg = {x: y for x, y in args.items()}
        msg['type'] = 'command'
        msg['operation'] = command
        msg['no_response'] = True
        packed = msgpack.packb(msg, use_bin_type=True)
        await self.con.send(packed)

    def _unpack(self, msg):
        """Unpack a binary msgpacked message."""

        return msgpack.unpackb(msg, raw=False, object_hook=self.decode_datetime)

    @classmethod
    def decode_datetime(cls, obj):
        """Decode a msgpack'ed datetime."""

        if b'__datetime__' in obj:
            obj = datetime.datetime.strptime(obj[b'as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        """Encode a msgpck'ed datetime."""

        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f").encode()}
        return obj

    async def _on_response_received(self, resp):
        """Put messages of "response" type on to the asyncio.Queue object"""

        await self.response_queue.put(resp)
