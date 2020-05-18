"""Implements authentication logic."""
import enum
import os
import struct
import hashlib
import hmac
from typing import Callable, Tuple
from iotile.core.hw.auth.auth_chain import ChainedAuthProvider
from iotile.core.exceptions import NotFoundError

class AuthType(enum.Enum):
    AUTH_METHOD_0 = 1 << 0 # Null Key
    AUTH_METHOD_1 = 1 << 1 # User Key
    AUTH_METHOD_2 = 1 << 2 # Device Key
    AUTH_METHOD_3 = 1 << 3 # Password based user key

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

"""A return type

Used in bled112 transport plug-in to convey results of communication to the device
bool is True when communication is successful and object is response
elsewise object conveys error reason
"""
TransportReturn = Tuple[bool, object]

"""A function pointer which implements means of communication with the BLE device.

The routine is expected to send a request to the server during the handshake procedure,
it is used to send both hello and verify messages,
The device expects that messages are sent one after another unless server hello conveys an error.
"""
SendAuthHandshakeFn = Callable[[bytes], TransportReturn]

class BLED112AuthManager:

    def __init__(self, permissions, token_generation):
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

    def _send_client_hello(self, supported_auth: int, handshake_fn: SendAuthHandshakeFn) -> TransportReturn:
        """Initiate the authentication process

        Tell the server what authentication methods it supports and the client nonce
        """
        self._client_nonce = bytearray(os.urandom(16))
        self._client_hello = struct.pack("xxxB16s", supported_auth, self._client_nonce)

        self._server_hello = handshake_fn(self._client_hello)
        if self._server_hello:
            generation, err, server_supported_auth, device_nonce = \
                struct.unpack("HBB16s", self._server_hello)
        else:
            return False, {"reason": "Did not receive server hello"}

        if err:
            return False, {"reason": "Server hello contains error code {}".format(err)}

        if generation > self._token_generation:
            return False, {"reason": "Server support only newer generation tokens {}".format(generation)}

        return True, (generation, server_supported_auth, device_nonce)

    def _send_client_verify(self, session_key: bytes, auth_type: int,
                            handshake_fn: SendAuthHandshakeFn) -> TransportReturn:

        """Verify session key between the client and the device"""
        verify_data = self._client_hello + self._server_hello
        client_verify = hmac.new(session_key, verify_data, hashlib.sha256).digest()[0:16]

        self._client_verify = struct.pack(
            "BBH16s", auth_type.value, self._permissions, self._token_generation, client_verify)

        server_verify = handshake_fn(self._client_verify)
        if server_verify:
            err, granted_permissions, server_verify = struct.unpack("BBxx16s", server_verify)
        else:
            return False, {"reason": "Did not received server verify"}

        if err:
            reason = "Client verify returned an error {}".format(err)
            if ERROR_CODES.get(err, None):
                reason = ERROR_CODES[err]

            return False, {"reason": reason}

        return True, (granted_permissions, server_verify)

    def _compute_session_key(self, root_key=None, user_token=None, scoped_token=None):
        if not scoped_token and not user_token and not root_key:
            return None

        if not scoped_token and not user_token:
            data = struct.pack("II", 0x01, self._token_generation)
            user_token = hmac.new(root_key, data, hashlib.sha256).digest()

        if not scoped_token:
            data = struct.pack("I", self._permissions)
            scoped_token = hmac.new(user_token, data, hashlib.sha256).digest()

        session_key = hmac.new(scoped_token, self._client_nonce + self._device_nonce, hashlib.sha256).digest()
        return session_key

    def _compute_server_verify(self, session_key):
        data = self._client_hello + self._server_hello + self._client_verify
        return hmac.new(session_key, data, hashlib.sha256).digest()[0:16]

    def _get_root_key(self, server_supported_auth, client_supported_auth, device_uuid):
        """Find a root key to authenticate connection to the POD device

            Look up is based to supported method by both client and server
            in order from DeviceKey to NullKey
        """
        supported_auth = server_supported_auth & client_supported_auth

        def _try_to_find_key(auth_method, key_type):
            _root_key = None
            if supported_auth & auth_method.value:
                try:
                    _root_key = self._key_provider.get_root_key(key_type=key_type, device_id=device_uuid)
                except NotFoundError:
                    pass
            return _root_key

        method_key_type_list = [ # order shows look up priority
            (AuthType.AUTH_METHOD_2, ChainedAuthProvider.DeviceKey),
            (AuthType.AUTH_METHOD_1, ChainedAuthProvider.UserKey),
            (AuthType.AUTH_METHOD_3, ChainedAuthProvider.PasswordBasedKey),
            (AuthType.AUTH_METHOD_0, ChainedAuthProvider.NullKey)
        ]

        for (method, key) in method_key_type_list:
            root_key = _try_to_find_key(method, key)
            if root_key:
                return root_key, method

        return None, None

    def authenticate(self, uuid, client_supported_auth, handshake_fn: SendAuthHandshakeFn) -> TransportReturn:
        """
        Perform authentication

        Args:
            uuid (int or str): either device mac or id
            auth_type (int): See .AuthType
            handshake_fn (SendAuthHandshakeFn): a function pointer
        Returns:
            (bool, bytearray/dict): tuple of success flag, session key or dict with reason of failure
        """
        result, response = self._send_client_hello(client_supported_auth, handshake_fn)
        if result:
            (_generation, server_supported_auth, self._device_nonce) = response
        else:
            return result, response

        root_key, auth_type = self._get_root_key(server_supported_auth, client_supported_auth, uuid)
        if root_key is None:
            return False, {"reason": "Root key is not found"}

        self._session_key = self._compute_session_key(root_key=root_key)

        result, response = self._send_client_verify(self._session_key, auth_type, handshake_fn)
        if result:
            (_granted_permissions, received_server_verify) = response
        else:
            return result, response

        computed_server_verify = self._compute_server_verify(self._session_key)
        if received_server_verify != computed_server_verify:
            return False, {"reason": "The device failed verification"}

        return True, self._session_key
