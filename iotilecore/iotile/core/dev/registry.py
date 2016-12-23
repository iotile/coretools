# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.utilities.kvstore import KeyValueStore
from iotile.core.exceptions import *
import json
import os.path
from iotileobj import IOTile
import pkg_resources
import imp

MISSING = object()

class ComponentRegistry:
    """
    ComponentRegistry

    A mapping of all of the installed components on this system that can
    be used as build dependencies and where they are located.  Also used
    to manage iotile plugins.
    """

    def __init__(self):
        self.kvstore = KeyValueStore('component_registry.db', respect_venv=True)
        self.plugins = {}
        
        for entry in pkg_resources.iter_entry_points('iotile.plugin'):
                plugin = entry.load()
                links = plugin()
                for name,value in links:
                    self.plugins[name] = value

    def add_component(self, component):
        """
        Register a component with ComponentRegistry. 

        Component must be a buildable object with a module_settings.json file that
        describes its name and the domain that it is part of.
        """

        tile = IOTile(component)
        value = os.path.normpath(os.path.abspath(component))

        self.kvstore.set(tile.name, value)

    def list_plugins(self):
        """
        List all of the plugins that have been registerd for the iotile program on this computer
        """

        vals = self.plugins.items()

        return {x: y for x,y in vals}

    def find_component(self, key, domain=""):
        try:
            if domain is not "":
                key = domain.lower() + '/' + key.lower()

            return IOTile(self.kvstore.get(key))
        except KeyError:
            raise ArgumentError("Unknown component name", name=key)

    def remove_component(self, key):
        """
        Remove component from registry
        """

        return self.kvstore.remove(key)

    def clear_components(self):
        """
        Clear all of the registered components
        """

        self.kvstore.clear()

    def list_components(self):
        """
        List all of the registered component names
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
        """Remvoe a persistent config key from the registry

        Args:
            key (string): The key name
        """

        keyname = "config:" + key
        self.kvstore.remove(keyname)
