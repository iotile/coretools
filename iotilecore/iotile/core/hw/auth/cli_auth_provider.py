
import os
import binascii
import struct
import hmac
import hashlib
from iotile.core.exceptions import NotFoundError
from .rootkey_auth_provider import RootKeyAuthProvider
from .env_auth_provider import EnvAuthProvider
from .auth_provider import AuthProvider
import getpass


class CliAuthProvider(RootKeyAuthProvider):
    """Key provider implementation that prompt user for password

       root key is derived using pbkdf2
    """
    def __init__(self, args=None):
        if args is None:
            args = {}

        args['supported_keys'] = [self.PasswordBasedKey]

        super().__init__(args)

    def get_root_key(self, key_type, device_id):
        """Prompt a user for the password and derive the root key from it

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): the uuid of the device

        Returns:
            bytes: the root key
        """
        self.verify_key(key_type)

        password = getpass.getpass("Please input the user password for the device {} :".format(device_id))
        userkey = AuthProvider.DeriveRebootKeyFromPassword(password)

        if device_id:
            answer = input("Would you like to save the user-key until the end of the current session? (y/n)")
            if answer and answer[0].lower() == 'y':
                variable_name = EnvAuthProvider.construct_var_name(device_id)
                os.environ[variable_name] = userkey.hex()

        return userkey
