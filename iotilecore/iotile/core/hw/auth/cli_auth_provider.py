
import os
import binascii
import struct
import hmac
import hashlib
from iotile.core.exceptions import NotFoundError
from .rootkey_auth_provider import RootKeyAuthProvider
import getpass


class CliAuthProvider(RootKeyAuthProvider):
    """Key provider implementation that prompt user for password

        root key is derived using pbkdf2
    """
    def __init__(self, args=None):
        if args is None:
            args = {}

        args['supported_keys'] = [self.UserKey]

        super().__init__(args)

    @classmethod
    def derive_key(cls, password):
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), b'salt', 100000)

    def get_root_key(self, key_type, device_id):
        """Prompt user for the password and derive root key from it"""
        self.verify_key(key_type)

        password = getpass.getpass("Please, input user password for device {} :".format(device_id))

        return CliAuthProvider.derive_key(password)
