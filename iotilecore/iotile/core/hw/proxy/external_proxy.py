# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

# external_proxy.py
# Routines for importing proxy modules from registered components on your computer

from iotile.core.dev.registry import ComponentRegistry
from iotile.core.exceptions import DataError
from .plugin import TileBusProxyPlugin


def find_proxy_plugin(component, plugin_name):
    """ Attempt to find a proxy plugin provided by a specific component

    Args:
        component (string): The name of the component that provides the plugin
        plugin_name (string): The name of the plugin to load

    Returns:
        TileBuxProxyPlugin: The plugin, if found, otherwise raises DataError
    """

    reg = ComponentRegistry()

    plugins = reg.load_extensions('iotile.proxy_plugin', comp_filter=component, class_filter=TileBusProxyPlugin,
                                  product_name='proxy_plugin')

    for _name, plugin in plugins:
        if plugin.__name__ == plugin_name:
            return plugin

    raise DataError("Could not find proxy plugin module in registered components or installed distributions",
                    component=component, name=plugin_name)
