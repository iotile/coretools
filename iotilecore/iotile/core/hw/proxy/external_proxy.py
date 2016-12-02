# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

# external_proxy.py
# Routines for importing proxy modules from registered components on your computer

import pkg_resources
from iotile.core.dev.registry import ComponentRegistry
from proxy import TileBusProxyObject
from plugin import TileBusProxyPlugin
from iotile.core.exceptions import *
import os
import imp
import inspect
import sys

def find_proxy(component, proxy_name=None, obj_type=TileBusProxyObject):
    """
    Search through the registered component data base for a proxy or proxy plugin module provided by
    a specific component optionally having a specific name.  

    Proxy modules must inherit from TileBusProxyObject. Proxy plugin modules must inherit from TileBusProxyPlugin
    """

    # Find all of the registered IOTile components and see if we need to add any proxies for them
    reg = ComponentRegistry()
    comp = reg.find_component(component)

    proxies = comp.proxy_modules()
    if len(proxies) != 1:
        raise DataError("Attempting to find proxy module from component that does not provide exactly 1 proxy", proxies=proxies)

    proxy_mod = proxies[0]

    proxy_objs = import_proxy(proxy_mod, obj_type)

    if len(proxy_objs) == 0:
        raise DataError("Specified component did not define any proxies but said that it did provide them", component=component)
    elif len(proxy_objs) > 1 and proxy_name is None:
        raise DataError("Sepcific component defined multiple proxy objects and a name was not specified", component=component, proxies=proxy_objs)
    elif len(proxy_objs) == 1 and proxy_name is None:
        return proxy_objs[0]

    for obj in proxy_objs:
        if obj.__name__ == proxy_name:
            return obj

    raise DataError("Named proxy could not be found", component=component, proxies=proxy_objs, desired_name=proxy_name)

def find_proxy_plugin(component, plugin_name):
    """ Attempt to find a proxy plugin provided by a specifc component
    
    Args:
        component (string): The name of the component that provides the plugin
        plugin_name (string): The name of the plugin to load

    Returns:
        TileBuxProxPlugin: The plugin, if found, otherwise raises DataError
    """

    reg = ComponentRegistry()

    #Try to find plugin in an installed component, otherwise look through installed
    #packages
    try:
        comp = reg.find_component(component)

        plugins = comp.proxy_plugins()

        for plugin in plugins:
            objs = import_proxy(plugin, TileBusProxyPlugin)
            for obj in objs:
                if obj.__name__ == plugin_name:
                    return obj
    except ArgumentError:
        pass

    for entry in pkg_resources.iter_entry_points('iotile.proxy_plugin'):
        module = entry.load()
        objs = [obj for obj in module.__dict__.itervalues() if inspect.isclass(obj) and issubclass(obj, TileBusProxyPlugin) and obj != TileBusProxyPlugin]
        for obj in objs:
            if obj.__name__ == plugin_name:
                return obj

    raise DataError("Could not find proxy plugin module in registered components or installed distributions", component=component, name=plugin_name)

def import_proxy(path, obj_type):
    """
    Add all proxy objects defined in the python module located at path.

    The module is loaded and all classes that inherit from the given object type
    are loaded and can be used to interact later with modules of that type.

    Returns the total number of proxies added.
    """

    d,p = os.path.split(path)

    p,ext = os.path.splitext(p)
    if ext != '.py' and ext != '.pyc' and ext != "":
        raise ArgumentError("Passed proxy module is not a python package or module (.py or .pyc)", path=path)

    try:
        fileobj,pathname,description = imp.find_module(p, [d])

        #Don't import twice if we've already imported this module
        if p in sys.modules:
            mod = sys.modules[p]
        else:
            mod = imp.load_module(p, fileobj, pathname, description)
    except ImportError as e:
        raise ArgumentError("could not import module in order to load external proxy modules", module_path=path, parent_directory=d, module_name=p, error=str(e))

    num_added = 0
    return [obj for obj in filter(lambda x: inspect.isclass(x) and issubclass(x, obj_type) and x != obj_type, mod.__dict__.itervalues())]
