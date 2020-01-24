import struct
from .rootkey_auth_provider import RootKeyAuthProvider

from iotile.core.exceptions import NotFoundError

class NullAuthProvider(RootKeyAuthProvider):
    """Auth provider that use null root key, uuid extended to 32 bytes with zeroes"""

    def __init__(self, args=None):
        if args is None:
            args = {}

        args['supported_keys'] = [self.NullKey]

        super().__init__(args)

    def get_root_key(self, key_type, device_id):
        self.verify_key(key_type)

        return bytearray(16)
