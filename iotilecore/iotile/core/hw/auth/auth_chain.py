"""An ordered list of authentication providers that are checked in turn to attempt to provide a key"""
from iotile.core.exceptions import NotFoundError, ExternalError
from iotile.core.dev import ComponentRegistry
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

        # FIXME: Allow overwriting default providers via args
        self._load_installed_providers()

        reg = ComponentRegistry()

        sub_providers = []
        for _, (priority, provider, provider_args) in reg.load_extensions('iotile.default_auth_providers'):
            if provider not in self._auth_factories:
                raise ExternalError("Default authentication provider list references unknown auth provider",
                                    provider_name=provider, known_providers=self._auth_factories.keys())
            configured = self._auth_factories[provider](provider_args)
            sub_providers.append((priority, configured))

        sub_providers.sort(key=lambda x: x[0])
        self.providers = sub_providers

    def _load_installed_providers(self):
        self._auth_factories = {}
        reg = ComponentRegistry()

        for name, entry in reg.load_extensions('iotile.auth_provider'):
            self._auth_factories[name] = entry

    def get_root_key(self, key_type, device_id):
        """Deligates call to auth providers in the chain

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): uuid of the device

        Returns:
            bytes: the root key
        """
        for _priority, provider in self.providers:
            try:
                return provider.get_root_key(key_type, device_id)
            except NotFoundError:
                pass

        raise NotFoundError("get_serialized_key method is not implemented in any sub_providers")

    def get_serialized_key(self, key_type, device_id, **key_info):
        """Deligates call to auth providers in the chain

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): uuid of the device
            key_info (dict): specific values for every auth provider

        Returns:
            bytes: the serialized key
        """
        for _priority, provider in self.providers:
            try:
                return provider.get_serialized_key(key_type, device_id, **key_info)
            except NotFoundError:
                pass

        raise NotFoundError("get_serialized_key method is not implemented in any sub_providers")

    def get_rotated_key(self, key_type, device_id, **rotation_info):
        """Deligates call to auth providers in the chain

        Args:
            key_type (int): see KnownKeyRoots
            device_id (int): uuid of the device
            rotation_info (dict): specific value for every auth provider

        Returns:
            bytes: the rotated key
        """
        for _priority, provider in self.providers:
            try:
                return provider.get_rotated_key(key_type, device_id, **rotation_info)
            except NotFoundError:
                pass

        raise NotFoundError("get_rotated_key method is not implemented in any sub_providers")

