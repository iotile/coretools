"""An ordered list of authentication providers that are checked in turn to attempt a crypto operation
"""

import pkg_resources
from auth_provider import AuthProvider, KnownSignatureMethods
from iotile.core.exceptions import NotFoundError, EnvironmentError

class ChainedAuthProvider(AuthProvider):
    """An AuthProvider that delegates operations to a list of subproviders

    Each subprovider is checked in turn and the first one able to satisfy a request
    is used.  If no provider is available that can perform an operation, NotFoundError
    is raised.

    By default, the python entry_point group 'iotile.default_auth_providers' is used
    to build the list of auth providers in the chain.  The entries in that group should
    be tuples of (priority, auth_provider_class, arg_dict) where priority is an integer,
    auth_provider_class is an AuthProvider subclass and arg_dict is a dictionary of 
    arguments passed to the constructor of auth_provider.
    """

    def __init__(self, args=None):
        #FIXME: Allow overwriting default providers via args
        self._load_installed_providers()

        sub_providers = []
        for entry in pkg_resources.iter_entry_points('iotile.default_auth_providers'):
            priority, provider, args = entry.load()

            if provider not in self._auth_factories:
                raise EnvironmentError("Default authentication provider list references unknown auth provider", provider_name=provider, known_providers=self._auth_factories.keys())
            configured = self._auth_factories[provider](args)
            sub_providers.append((priority, configured))

        sub_providers.sort(key=lambda x: x[0])
        self.providers = sub_providers

    def _load_installed_providers(self):
        self._auth_factories = {}

        for entry in pkg_resources.iter_entry_points('iotile.auth_provider'):
            self._auth_factories[entry.name] = entry.load()

    def encrypt(self, device_id, enc_method, data):
        """Encrypt a buffer of data on behalf of a device

        Args:
            device_id (int): The id of the device that we should encrypt for
            enc_method (int): The method of encryption that we should perform
            data (bytearray): The data that we should encrypt

        Returns:
            dict: The encrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        for priority, provider in self.providers:
            try:
                return provider.encrypt(device_id, enc_method, data)
            except NotFoundError:
                pass

        raise NotFoundError("encrypt method is not implemented in any sub_providers")

    def decrypt(self, device_id, enc_method, data):
        """Decrypt a buffer of data on behalf of a device

        Args:
            device_id (int): The id of the device that we should encrypt for
            enc_method (int): The method of encryption that we should perform
            data (bytearray): The data that we should encrypt

        Returns:
            dict: The decrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        for priority, provider in self.providers:
            try:
                return provider.decrypt(device_id, enc_method, data)
            except NotFoundError:
                pass

        raise NotFoundError("decrypt method is not implemented in any sub_providers")

    def sign(self, device_id, sig_method, data):
        """Sign a buffer of data on behalf of a device

        Args:
            device_id (int): The id of the device that we should encrypt for
            sig_method (int): The method of encryption that we should perform
            data (bytearray): The data that we should sign

        Returns:
            dict: The signature and any associated metadata about the signature.
                The signatured itself must always be a bytearray stored under the 
                'signature' key, however additional keys may be present depending 
                on the signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        for priority, provider in self.providers:
            try:
                return provider.sign(device_id, sig_method, data)
            except NotFoundError:
                pass

        raise NotFoundError("sign method is not implemented in any sub_providers")

    def verify(self, device_id, sig_method, data, signature):
        """Verify the signature attached to a buffer of data

        Args:
            device_id (int): The id of the device that we should encrypt for
            sig_method (int): The method of signing that was used
            data (bytearray): The data whose signature we should verify
            signature (bytearray): The signature attached to data

        Returns:
            dict: The result of the verification process must always be a bool under the
                'verified' key, however additional keys may be present depending on the 
                signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        for priority, provider in self.providers:
            try:
                return provider.verify(device_id, sig_method, data, signature)
            except NotFoundError:
                pass

        raise NotFoundError("verify method is not implemented in any sub_providers")
