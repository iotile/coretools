import os
import binascii
import struct
import hmac
import hashlib
from iotile.core.exceptions import NotFoundError
from .rootkey_auth_provider import RootKeyAuthProvider


class EnvAuthProvider(RootKeyAuthProvider):
    """Key provider implementation that search for keys in environment"""

    def __init__(self, args=None):
        if args is None:
            args = {}

        args['supported_keys'] = [self.UserKey]

        super().__init__(args)

    @classmethod
    def construct_var_name(cls, device_id):
        """Build name of environment variable used to store userkey

        Returns:
            str: variable name
        """
        if isinstance(device_id, str):
            var_name = "USER_KEY_{}".format(device_id)
        else:
            var_name = "USER_KEY_{0:08X}".format(device_id)
        return var_name

    def get_root_key(self, key_type, device_id):
        """Attempt to get a user key from an environment variable

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): uuid of the device

        Returns:
            bytes: the root key
        """
        self.verify_key(key_type)

        var_name = EnvAuthProvider.construct_var_name(device_id)

        if var_name not in os.environ:
            raise NotFoundError("No key could be found for devices", device_id=device_id,
                                expected_variable_name=var_name)

        key_var = os.environ[var_name]
        if len(key_var) != 64:
            raise NotFoundError("Key in variable is not the correct length, should be 64 hex characters",
                                device_id=device_id, key_value=key_var)
        try:
            key = binascii.unhexlify(key_var)
        except ValueError as exc:
            raise NotFoundError("Key in variable could not be decoded from hex", device_id=device_id,
                                key_value=key_var) from exc

        if len(key) != 32:
            raise NotFoundError("Key in variable is not the correct length, should be 64 hex characters",
                                device_id=device_id, key_value=key_var)

        return key
