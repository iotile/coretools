"""A websocket client that validates messages received and dispatches them."""

from ws4py.client.threadedclient import WebSocketClient
import threading
import msgpack
import datetime
import logging
from iotile.core.exceptions import IOTileException, InternalError, ValidationError, TimeoutExpiredError
from iotile.core.utilities.schema_verify import Verifier, DictionaryVerifier, StringVerifier, LiteralVerifier, OptionsVerifier

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


class ValidatingWSClient(WebSocketClient):
    """A threaded websocket client that validates messages received.

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

        super(ValidatingWSClient, self).__init__(url)

        self._connected = threading.Event()
        self._disconnection_finished = threading.Event()

        self._command_lock = threading.Lock()

        self._last_response = None
        self._response_received = threading.Event()

        self.disconnection_code = None
        self.disconnection_reason = None

        self.logger = logging.getLogger(logger_name)
        self.logger.addHandler(logging.NullHandler())

        self.validators = [(ResponseSchema, self._on_response_received)]

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

    def start(self, timeout=5.0):
        """Synchronously connect to websocket server.

        Args:
            timeout (float): The maximum amount of time to wait for the
                connection to be established. Defaults to 5 seconds
        """

        try:
            self.connect()
        except Exception, exc:
            raise InternalError("Unable to connect to websockets host", reason=str(exc))

        flag = self._connected.wait(timeout=timeout)
        if not flag:
            raise TimeoutExpiredError("Conection attempt to host timed out")

    def stop(self, timeout=5.0):
        """Synchronously disconnect from websocket server.

        Args:
            timeout (float): The maximum amount of time to wait for the
                connection to be established. Defaults to 5 seconds
        """

        if not self._connected.is_set():
            return

        try:
            self.close()
        except Exception, exc:
            raise InternalError("Unable to disconnect from websockets host", reason=str(exc))

        flag = self._disconnection_finished.wait(timeout=timeout)
        if not flag:
            raise TimeoutExpiredError("Disconnection attempt from host timed out")

    def send_message(self, obj):
        """Send a packed message.

        Args:
            obj (dict): The message to be sent
        """

        packed = msgpack.packb(obj)
        self.send(packed, binary=True)

    def send_command(self, command, args, timeout=10.0):
        """Send a command any synchronously wait for a response.

        Args:
            command (string): The command name
            args (dict): Optional arguments
            timeout (float): The maximum time to wait for a response
        """

        msg = {x: y for x, y in args.iteritems()}
        msg['type'] = 'command'
        msg['operation'] = command
        msg['no_response'] = False

        with self._command_lock:
            self._response_received.clear()
            self.send_message(msg)

            flag = self._response_received.wait(timeout=timeout)
            if not flag:
                raise TimeoutExpiredError("Timeout waiting for response")

            self._response_received.clear()
            return self._last_response

    def post_command(self, command, args):
        """Post a command asynchronously and don't wait for a response.

        Args:
            command (string): The command name
            args (dict): Optional arguments
        """

        msg = {x: y for x, y in args.iteritems()}
        msg['type'] = 'command'
        msg['operation'] = command
        msg['no_response'] = True

        self.send_message(msg)

    def opened(self):
        """Callback called in another thread when a connection is opened."""

        self._connected.set()

    def closed(self, code, reason):
        """Callback called in another thread when a connection is closed.

        Args:
            code (int): A code for the closure
            reason (string): A reason for the closure
        """

        self.disconnection_code = code
        self.disconnection_reason = reason
        self._disconnection_finished.set()
        self._connected.clear()

    def _unpack(self, msg):
        """Unpack a binary msgpacked message."""

        return msgpack.unpackb(msg, object_hook=self.decode_datetime)

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

    def received_message(self, message):
        """Callback when a message is received.

        The message must be encoded using message_mack

        Args:
            message (object): The message that was received
        """

        try:
            unpacked = self._unpack(message.data)
        except Exception, exc:
            self.logger.error("Corrupt message received, parse exception = %s", str(exc))
            return

        # Look for the first callback that can handle this message
        # if no one can handle it, log an error and discard the message.
        for validator, callback in self.validators:
            try:
                validator.verify(unpacked)
            except ValidationError, exc:
                continue

            try:
                callback(unpacked)
                return
            except IOTileException, exc:
                self.logger.error("Exception handling websocket message, exception = %s", str(exc))
            except Exception, exc:
                self.logger.error("Non-IOTile exception handling websocket message, exception = %s", str(exc))

        self.logger.warn("No handler found for received message, message=%s", str(unpacked))

    def _on_response_received(self, resp):
        self._last_response = resp
        self._response_received.set()
