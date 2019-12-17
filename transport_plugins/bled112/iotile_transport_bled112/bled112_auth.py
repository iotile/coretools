"""
    Implements authentication logic.

    Used with command processor that implement a routine:

    command_processor.send_auth_client_request(payload, *additional_args) -> (bool, bytearray)
        The routine is expected to send a request to server, used to send both hello and verify messages,
        The device expects that messages are sent one after another unless server hello convey an error
"""
import enum
import os
import struct
import hashlib
import hmac
from iotile.core.hw.auth.auth_chain import ChainedAuthProvider

class AuthType(enum.Enum):
    AUTH_METHOD_0 = 1 << 0 # Null Key
    AUTH_METHOD_1 = 1 << 1 # User Key
    AUTH_METHOD_2 = 1 << 2 # Device Key

class State(enum.Enum):
    NOT_AUTHENTICATED = 0
    AUTHENTICATION_IN_PROGRESS = 1
    AUTHENTICATED = 2

ERROR_CODES = {
    2: "Client token is too old",
    3: "Client verify is incorrect, please make sure your password is correct",
    4: "Client timeout",
    5: "Unacceptable client authentication method"
}

class BLED112AuthManager:

    def __init__(self, supported_auth, permissions, token_generation):
        self._supported_auth = supported_auth
        self._permissions = permissions
        self._token_generation = token_generation

        self._client_nonce = None
        self._device_nonce = None

        self._session_key = None

        self._client_hello = None
        self._server_hello = None
        self._client_verify = None

        self._key_provider = ChainedAuthProvider()

        self._state = State.NOT_AUTHENTICATED

    def _send_client_hello(self, command_processor, *command_processor_args):
        """Initiate the authentication process

        Tell the server what authentication methods it supports and nonce
        """
        self._client_nonce = bytearray(b"\x02" * 16) #bytearray.fromhex(os.urandom(16))
        self._client_hello = struct.pack("xxxB16s", self._supported_auth, self._client_nonce)

        return command_processor.send_auth_client_request(self._client_hello, *command_processor_args)

    def _send_client_verify(self, session_key, auth_type, command_processor, *command_processor_args):
        """Verify session key between the client and the device"""
        client_verify = hmac.new(session_key, self._client_hello + self._server_hello, hashlib.sha256).digest()[0:16]
        self._client_verify = struct.pack("BBH16s", auth_type, self._permissions, self._token_generation, client_verify)

        server_verify = command_processor.send_auth_client_request(self._client_verify, *command_processor_args)
        err, granted_permissions, server_verify = struct.unpack("BBxx16s", server_verify)

        return err, granted_permissions, server_verify

    def _compute_session_key_security_level_1(self, root_key=None, user_token=None, scoped_token=None):
        if not scoped_token and not user_token and not root_key:
            return None

        if not scoped_token and not user_token:
            data = struct.pack("II", 0x01, self._token_generation)
            user_token = hmac.new(root_key, data, hashlib.sha256).digest()

        if not scoped_token:
            data = struct.pack("I",  self._permissions)
            scoped_token = hmac.new(user_token, data, hashlib.sha256).digest()

        session_key = hmac.new(scoped_token, self._client_nonce + self._device_nonce, hashlib.sha256).digest()
        return session_key

    def _compute_session_key_security_level_0(self, uuid=b'\x00'):
        scoped_token = uuid + b'\x00' * (32 - len(uuid)) #FIXME uuid
        return self._compute_session_key_security_level_1(scoped_token=scoped_token)

    def _compute_server_verify(self, session_key):
        data = self._client_hello + self._server_hello + self._client_verify
        return hmac.new(session_key, data, hashlib.sha256).digest()[0:16]

    def authenticate(self, uuid, auth_type, command_processor, *command_processor_args):
        """
        Perform authentication

        Args:
            uuid (int or str): either device mac or id
            auth_type (int): See .AuthType
            command_processor (obj): an object with member functions `send_auth_client_request` which
                implements mean of communication with server, specification below
                command_processor.send_auth_client_request(payload, *command_processor_args) -> (bool, bytearray)
                    The routine is expected to send a request to server, used to send both hello and verify messages,
                    The device expects that messages are sent one after another unless server hello convey an error
        Returns:
            (bool, bytearray/dict): tuple of success flag, sessin key or dict with reason of failure
        """
        required_method = getattr(command_processor, "send_auth_client_request", None)
        if not required_method or not callable(required_method):
            return False, {"reason": "command_processor should implement send_auth_client_request"}

        self._server_hello = self._send_client_hello(command_processor, *command_processor_args)
        generation, err, server_supported_auth, self._device_nonce = struct.unpack("HBB16s", self._server_hello)

        if err:
            return False, {"reason": "Server hello contains error code {}".format(err)}

        if generation > self._token_generation:
            return False, {"reason": "Server support only newer generation tokens {}".format(generation)}

        try:
            auth_method = AuthType(auth_type)
        except ValueError:
            return False, {"reason": "Auth type {} does not exist".format(auth_method)}

        if server_supported_auth & auth_type == 0:
            return False, {"reason": "{} is not supported, bitmap of supported: {}".format(auth_method, bin(server_supported_auth))}

        if auth_method == AuthType.AUTH_METHOD_0:
            self._session_key = self._compute_session_key_security_level_0()
        elif auth_method == AuthType.AUTH_METHOD_1:
            root_key = self._key_provider.get_root_key(key_type=ChainedAuthProvider.UserKey, device_id=uuid)
            self._session_key = self._compute_session_key_security_level_1(root_key=root_key)
        else:
            return False, {"reason": "Auth type is not implemented {}".format(auth_method)}

        err, granted_permissions, received_server_verify = \
            self._send_client_verify(self._session_key, auth_type, command_processor, *command_processor_args)

        if err:
            reason = "Client verify returned an error {}".format(err)
            if err in ERROR_CODES:
                reason = ERROR_CODES[err]

            return False, {"reason": reason}

        computed_server_verify = self._compute_server_verify(self._session_key)
        if received_server_verify != computed_server_verify:
            return False, {"reason": "The device failed verification"}

        return True, self._session_key

