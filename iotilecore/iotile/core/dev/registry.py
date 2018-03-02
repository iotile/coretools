# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.utilities.kvstore_sqlite import SQLiteKVStore
from iotile.core.utilities.kvstore_json import JSONKVStore
from iotile.core.utilities.kvstore_mem import InMemoryKVStore
from iotile.core.exceptions import *
from iotile.core.utilities.paths import settings_directory
import json
import os.path
from .iotileobj import IOTile
import pkg_resources
import imp
import sys

MISSING = object()

class ComponentRegistry(object):
    """
    ComponentRegistry

    A mapping of all of the installed components on this system that can
    be used as build dependencies and where they are located.  Also used
    to manage iotile plugins.
    """

    BackingType = SQLiteKVStore
    BackingFileName = 'component_registry.db'

    def __init__(self):
        self.kvstore = self.BackingType(self.BackingFileName, respect_venv=True)
        self._plugins = None

    @property
    def plugins(self):
        """Lazily load iotile plugins only on demand.

        This is a slow operation on computers with a slow FS and
        is rarely accessed information, so only compute it when it
        is actually asked for.
        """

        if self._plugins is None:
            self._plugins = {}

            for entry in pkg_resources.iter_entry_points('iotile.plugin'):
                plugin = entry.load()
                links = plugin()
                for name, value in links:
                    self._plugins[name] = value

        return self._plugins

    @classmethod
    def SetBackingStore(cls, backing):
        """Set the global backing type used by the ComponentRegistry from this point forward

        This function must be called before any operations that use the registry are initiated
        otherwise they will work from different registries that will likely contain different data
        """

        if backing not in ['json', 'sqlite', 'memory']:
            raise ArgumentError("Unknown backing store type that is not json or sqlite", backing=backing)

        if backing == 'json':
            cls.BackingType = JSONKVStore
            cls.BackingFileName = 'component_registry.json'
        elif backing == 'memory':
            cls.BackingType = InMemoryKVStore
            cls.BackingFileName = None
        else:
            cls.BackingType = SQLiteKVStore
            cls.BackingFileName = 'component_registry.db'

    def add_component(self, component):
        """
        Register a component with ComponentRegistry.

        Component must be a buildable object with a module_settings.json file that
        describes its name and the domain that it is part of.
        """

        tile = IOTile(component)
        value = os.path.normpath(os.path.abspath(component))

        self.kvstore.set(tile.name, value)

    def get_component(self, component):
        try:
            comp_path = self.kvstore.get(component)
        except KeyError:
            raise ArgumentError("Could not find component by name", component=component)

        return IOTile(comp_path)

    def list_plugins(self):
        """
        List all of the plugins that have been registerd for the iotile program on this computer
        """

        vals = self.plugins.items()

        return {x: y for x, y in vals}

    def find_component(self, key, domain=""):
        try:
            if domain is not "":
                key = domain.lower() + '/' + key.lower()

            return IOTile(self.kvstore.get(key))
        except KeyError:
            raise ArgumentError("Unknown component name", name=key)

    def remove_component(self, key):
        """Remove component from registry
        """

        return self.kvstore.remove(key)

    def clear_components(self):
        """Clear all of the registered components
        """

        for key in self.list_components():
            self.remove_component(key)

    def clear(self):
        """Clear all data from the registry
        """

        self.kvstore.clear()

    def list_components(self):
        """List all of the registered component names
        """

        items = self.kvstore.get_all()

        return [x[0] for x in items if not x[0].startswith('config:')]

    def set_config(self, key, value):
        """Set a persistent config key to a value, stored in the registry

        Args:
            key (string): The key name
            value (string): The key value
        """

        keyname = "config:" + key

        self.kvstore.set(keyname, value)

    def get_config(self, key, default=MISSING):
        """Get the value of a persistent config key from the registry

        If no default is specified and the key is not found ArgumentError is raised.

        Args:
            key (string): The key name to fetch
            default (string): an optional value to be returned if key cannot be found

        Returns:
            string: the key's value
        """

        keyname = "config:" + key

        try:
            return self.kvstore.get(keyname)
        except KeyError:
            if default is MISSING:
                raise ArgumentError("No config value found for key", key=key)

            return default

    def clear_config(self, key):
        """Remove a persistent config key from the registry

        Args:
            key (string): The key name
        """

        keyname = "config:" + key
        self.kvstore.remove(keyname)


def _check_registry_type(folder=None):
    """Check if the user has placed a registry_type.txt file to choose the registry type

    If a default registry type file is found, the DefaultBackingType and DefaultBackingFile
    class parameters in ComponentRegistry are updated accordingly.

    Args:
        folder (string): The folder that we should check for a default registry type
    """

    if folder is None:
        folder = settings_directory()

    #If we are relative to a virtual environment, place the registry into that virtual env
    #Support both virtualenv and pythnon 3 venv
    if hasattr(sys, 'real_prefix'):
        folder = sys.prefix
    elif hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix:
        folder = sys.prefix

    default_file = os.path.join(folder, 'registry_type.txt')

    try:
        with open(default_file, "rb") as infile:
            data = infile.read()
            data = data.strip()

            ComponentRegistry.SetBackingStore(data)
    except IOError:
        pass

# Update our default registry backing store appropriately
_check_registry_type()
