from iotile.core.exceptions import NotFoundError
from .rootkey_auth_provider import RootKeyAuthProvider
from .auth_provider import AuthProvider


class InMemoryAuthProvider(RootKeyAuthProvider):
    """Key provider implementation that allows user to set a password in memory"""

    _shared_passwords = {}

    def __init__(self, args=None):
        if args is None:
            args = {}

        args['supported_keys'] = [self.PasswordBasedKey]

        super().__init__(args)

    @classmethod
    def add_password(cls, device_id, password):
        """Adds a password to the class

        Args:
            device_id (int): uuid or mac of the device
            password (str): password to the device
        """
        key = AuthProvider.DeriveRebootKeyFromPassword(password)
        cls._shared_passwords[device_id] = key

    @classmethod
    def clear_password(cls, device_id):
        """Clears a password from the class

        Args:
            device_id (int): uuid or mac of the device
        """
        cls._shared_passwords.pop(device_id, None)

    @classmethod
    def get_password(cls, device_id):
        """Returns the password from the class

        Args:
            device_id (int): uuid or mac of the device

        Returns:
            bytes: the root key
        """
        if device_id in cls._shared_passwords:
            return cls._shared_passwords[device_id]
        else:
            raise NotFoundError("No key could be found for device", device_id=device_id)

    def get_root_key(self, key_type, device_id):
        """Attempt to get a user key from memory

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): uuid or mac of the device

        Returns:
            bytes: the root key
        """
        self.verify_key(key_type)

        return InMemoryAuthProvider.get_password(device_id)
