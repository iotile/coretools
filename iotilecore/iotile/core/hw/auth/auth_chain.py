"""An ordered list of authentication providers that are checked in turn to attempt a crypto operation
"""

import pkg_resources
from iotile.core.exceptions import NotFoundError, ExternalError
from .auth_provider import AuthProvider


class ChainedAuthProvider(AuthProvider):
    """An AuthProvider that delegates operations to a list of subproviders.

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
        super(ChainedAuthProvider, self).__init__(args)

        #FIXME: Allow overwriting default providers via args
        self._load_installed_providers()

        sub_providers = []
        for entry in pkg_resources.iter_entry_points('iotile.default_auth_providers'):
            priority, provider, args = entry.load()

            if provider not in self._auth_factories:
                raise ExternalError("Default authentication provider list references unknown auth provider", provider_name=provider, known_providers=self._auth_factories.keys())
            configured = self._auth_factories[provider](args)
            sub_providers.append((priority, configured))

        sub_providers.sort(key=lambda x: x[0])
        self.providers = sub_providers

    def _load_installed_providers(self):
        self._auth_factories = {}

        for entry in pkg_resources.iter_entry_points('iotile.auth_provider'):
            self._auth_factories[entry.name] = entry.load()

    def encrypt_report(self, device_id, root, data, **kwargs):
        """Encrypt a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should encrypt.
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The encrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        for _priority, provider in self.providers:
            try:
                return provider.encrypt_report(device_id, root, data, **kwargs)
            except NotFoundError:
                pass

        raise NotFoundError("encrypt_report method is not implemented in any sub_providers")

    def decrypt_report(self, device_id, root, data, **kwargs):
        """Encrypt a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should decrypt
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The encrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to decrypt the data.
        """

        for _priority, provider in self.providers:
            try:
                return provider.decrypt_report(device_id, root, data, **kwargs)
            except NotFoundError:
                pass

        raise NotFoundError("decrypt_report method is not implemented in any sub_providers")

    def sign_report(self, device_id, root, data, **kwargs):
        """Sign a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should sign
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The signature and any associated metadata about the signature.
                The signature itself must always be a bytearray stored under the
                'signature' key, however additional keys may be present depending
                on the signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to sign the data.
        """

        for _priority, provider in self.providers:
            try:
                return provider.sign_report(device_id, root, data, **kwargs)
            except NotFoundError:
                pass

        raise NotFoundError("sign_report method is not implemented in any sub_providers")

    def verify_report(self, device_id, root, data, signature, **kwargs):
        """Verify a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should verify
            signature (bytearray): The signature attached to data that we should verify
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The result of the verification process must always be a bool under the
                'verified' key, however additional keys may be present depending on the
                signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to verify the data due to
                an error.  If the data is simply not valid, then the function returns
                normally.
        """

        for _priority, provider in self.providers:
            try:
                return provider.verify_report(device_id, root, data, signature, **kwargs)
            except NotFoundError:
                pass

        raise NotFoundError("verify_report method is not implemented in any sub_providers")
