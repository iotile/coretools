from iotile.core.exceptions import NotFoundError
from .rootkey_auth_provider import RootKeyAuthProvider
from .auth_provider import AuthProvider


class InMemoryAuthProvider(RootKeyAuthProvider):
    """Key provider implementation that allows user to set a password in memory"""

    def __init__(self, args=None):
        if args is None:
            args = {}

        args['supported_keys'] = [self.PasswordBasedKey]
        self.keys = {}

        super().__init__(args)

    def add_password(self, device_id, password):
        """Adds a password to the instance

        Args:
            device_id (int): uuid or mac of the device
            password (str): password to the device

        """
        key = AuthProvider.DeriveRebootKeyFromPassword(password)
        self.keys[str(device_id)] = key

    def get_root_key(self, key_type, device_id):
        """Attempt to get a user key from memory

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): uuid or mac of the device

        Returns:
            bytes: the root key
        """
        self.verify_key(key_type)

        if str(device_id) not in self.keys:
            raise NotFoundError("No key could be found for devices", device_id=device_id)

        return self.keys[str(device_id)]
