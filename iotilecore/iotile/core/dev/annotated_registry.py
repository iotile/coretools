# Annotated Registry
# A wrapper to make the IOTile component registry accessible in the iotile
# tool.  Since the registry is used internally in the type system it cannot
# itself make use of typedargs annotations
from iotile.core.utilities.typedargs import annotated, param, return_type, context
from iotile.core.utilities.typedargs.annotate import docannotate
from iotile.core.exceptions import ExternalError
from iotile.core.hw.auth.inmemory_auth_provider import InMemoryAuthProvider
from .registry import ComponentRegistry

_name_ = "Developer"


@docannotate
def registry():
    """Returns an Annotated Registry

    Returns:
        AnnotatedRegistry show-as context: an Annotated Registry
    """
    return AnnotatedRegistry()

@context()
class AnnotatedRegistry(object):
    """AnnotatedRegistry

    A mapping of all of the installed components on this system that can
    be used as build dependencies and where they are located.  Also used
    to manage iotile plugins.
    """

    def __init__(self):
        self.reg = ComponentRegistry()

    @docannotate
    def add_component(self, component):
        """Register a component with ComponentRegistry.

        Component must be a buildable object with a module_settings.json file that
        describes its name and the domain that it is part of.

        Args:
            component (path): folder containing component to register
        """

        self.reg.add_component(component)

    @docannotate
    def list_plugins(self):
        """List all of the plugins that have been registerd for the iotile program on this computer
        
        Returns:
            map(string, string): List of plugins registered for this iotile instance
        """

        return self.reg.list_plugins()

    def find_component(self, key, domain=""):
        return self.reg.find_component(key, domain)

    @docannotate
    def remove_component(self, key):
        """Remove component from registry

        Args:
            key (str): iotile component to remove
        """

        return self.reg.remove_component(key)

    @docannotate
    def clear_components(self):
        """Clear all of the registered components
        """

        self.reg.clear_components()

    @docannotate
    def list_components(self):
        """List all of the registered component names

        Returns:
            list(string): list of the registered component names
        """

        return self.reg.list_components()

    @docannotate
    def list_config(self):
        """List all of the registered config names

        Returns:
            list(string): list of registered config names
        """

        return self.reg.list_config()

    @docannotate
    def set_temporary_password(self, device_uuid: int, password: str):
        """Sets a temporary password for a device in memory for the current instance.

        Args:
            device_uuid (int): the device UUID
            password (str): the password to save in memory
        """
        InMemoryAuthProvider.add_password(device_uuid, password)

    @docannotate
    def clear_temporary_password(self, device_uuid: int):
        """Clears the password based on the device UUID

        Args:
            device_uuid (int): the device UUID
        """
        InMemoryAuthProvider.clear_password(device_uuid)

    @docannotate
    def set(self, key, value):
        """Sets a config value in the registry to a value

        Args:
            key (str): the config variable
            value (str): the value to be set
        """
        self.reg.set_config(key, value)

    @docannotate
    def get(self, key):
        """Gets a config value from its key in the registry

        Args:
            key (str): the config variable

        Returns:
            string: the value of the config variable
        """
        return self.reg.get_config(key)

    @docannotate
    def clear(self, key):
        """Clears a config key from the registry

        Args:
            key (str): the config variable
        """
        self.reg.clear_config(key)

    @docannotate
    def freeze(self):
        """Freeze the current list of extensions to a single file.

        This speeds up the extension loading process but does not check for
        new extensions each time the program is run. You should only use this
        method in situations where you know the extension list is static
        and you need the speedup benefits.

        You can undo this by calling unfreeze().
        """

        self.reg.freeze_extensions()

    @docannotate
    def unfreeze(self):
        """Remove any frozen extension list."""

        try:
            self.reg.unfreeze_extensions()
        except ExternalError:
            pass  # This means there was no frozen list of extensions
