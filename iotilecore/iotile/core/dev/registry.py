# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import os.path
import sys
import logging
import imp
import inspect
from types import ModuleType
from future.utils import itervalues
from past.builtins import basestring

from iotile.core.utilities.kvstore_sqlite import SQLiteKVStore
from iotile.core.utilities.kvstore_json import JSONKVStore
from iotile.core.utilities.kvstore_mem import InMemoryKVStore
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities.paths import settings_directory
from .iotileobj import IOTile

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

    _registered_extensions = {}
    _component_overlays = {}

    def __init__(self):
        self._kvstore = None
        self._plugins = None
        self._logger = logging.getLogger(__name__)

    @property
    def kvstore(self):
        """Lazily load the underlying key-value store backing this registry."""

        if self._kvstore is None:
            self._kvstore = self.BackingType(self.BackingFileName, respect_venv=True)

        return self._kvstore

    @property
    def plugins(self):
        """Lazily load iotile plugins only on demand.

        This is a slow operation on computers with a slow FS and is rarely
        accessed information, so only compute it when it is actually asked
        for.
        """

        if self._plugins is None:
            import pkg_resources

            self._plugins = {}

            for entry in pkg_resources.iter_entry_points('iotile.plugin'):
                plugin = entry.load()
                links = plugin()
                for name, value in links:
                    self._plugins[name] = value

        return self._plugins

    def load_extensions(self, group, name_filter=None, comp_filter=None, class_filter=None, product_name=None, unique=False):
        """Dynamically load and return extension objects of a given type.

        This is the centralized way for all parts of CoreTools to allow plugin
        behavior.  Whenever a plugin is needed, this method should be called
        to load it.  Examples of plugins are proxy modules, emulated tiles,
        iotile-build autobuilders, etc.

        Each kind of plugin will typically be a subclass of a certain base class
        and can be provided one of three ways:

        1. It can be registered as an entry point in a pip installed package.
           The entry point group must map the group passed to load_extensions.
        2. It can be listed as a product of an IOTile component that is stored
           in this ComponentRegistry.  The relevant python file inside the
           component will be imported dynamically as needed.
        3. It can be programmatically registered by calling ``register_extension()``
           on this class with a string name and an object.  This is equivalent to
           exposing that same object as an entry point with the given name.

        There is special behavior of this function if class_filter is passed
        and the object returned by one of the above three methods is a python
        module. The module will be search for object definitions that match
        the defined class.

        The order of the returned objects list is only partially defined.
        Locally installed components are searched before pip installed
        packages with entry points.  The order of results within each group is
        not specified.

        Args:
            group (str): The extension type that you wish to enumerate.  This
                will be used as the entry_point group for searching pip
                installed packages.
            name_filter (str): Only return objects with the given name
            comp_filter (str): When searching through installed components
                (not entry_points), only search through components with the
                given name.
            class_filter (type or tuple of types): An object that will be passed to
                instanceof() to verify that all extension objects have the correct
                types.  If not passed, no checking will be done.
            product_name (str): If this extension can be provided by a registered
                local component, the name of the product that should be loaded.
            unique (bool): If True (default is False), there must be exactly one object
                found inside this extension that matches all of the other criteria.

        Returns:
            list of (str, object): A list of the found and loaded extension objects.

            The string returned with each extension is the name of the
            entry_point or the base name of the file in the component or the
            value provided by the call to register_extension depending on how
            the extension was found.

            If unique is True, then the list only contains a single entry and that
            entry will be directly returned.
        """

        found_extensions = []

        import pkg_resources

        if product_name is not None:
            for comp in self.iter_components():
                if comp_filter is not None and comp != comp_filter:
                    continue

                products = comp.find_products(product_name)
                for product in products:
                    try:
                        entries = self.load_extension(product, name_filter=name_filter, class_filter=class_filter)

                        if len(entries) == 0:
                            self._logger.warn("Found no valid extensions in product %s of component %s", product, comp.path)
                            continue

                        found_extensions.extend(entries)
                    except:  #pylint:disable=bare-except;We don't want a broken extension to take down the whole system
                        self._logger.exception("Unable to load extension %s from local component %s at path %s", product_name, comp, product)

        for entry in pkg_resources.iter_entry_points(group):
            name = entry.name

            if name_filter is not None and name != name_filter:
                continue

            ext = entry.load()

            found_extensions.extend((name, x) for x in self._filter_subclasses(ext, class_filter))

        for (name, ext) in self._registered_extensions.get(group, []):
            if name_filter is not None and name != name_filter:
                continue

            found_extensions.extend((name, x) for x in self._filter_subclasses(ext, class_filter))

        found_extensions = [(name, x) for name, x in found_extensions if self._filter_nonextensions(x)]

        if unique is True:
            if len(found_extensions) > 1:
                raise ArgumentError("Extension %s should have had exactly one instance of class %s, found %d" % (group, class_filter.__name__, len(found_extensions)), classes=found_extensions)
            elif len(found_extensions) == 0:
                raise ArgumentError("Extension %s had no instances of class %s" % (group, class_filter.__name__))

            return found_extensions[0]

        return found_extensions

    def register_extension(self, group, name, extension):
        """Register an extension.

        Args:
            group (str): The type of the extension
            name (str): A name for the extension
            extension (str or class): If this is a string, then it will be
                interpreted as a path to import and load.  Otherwise it
                will be treated as the extension object itself.
        """

        if isinstance(extension, basestring):
            name, extension = self.load_extension(extension)[0]

        if group not in self._registered_extensions:
            self._registered_extensions[group] = []

        self._registered_extensions[group].append((name, extension))

    def clear_extensions(self, group=None):
        """Clear all previously registered extensions."""

        if group is None:
            self._registered_extensions = {}
            return

        if group in self._registered_extensions:
            self._registered_extensions[group] = []

    def load_extension(self, path, name_filter=None, class_filter=None, unique=False):
        """Load a single python module extension.

        This function is similar to using the imp module directly to load a
        module and potentially inspecting the objects it declares to filter
        them by class.

        Args:
            path (str): The path to the python file to load
            name_filter (str): If passed, the basename of the module must match
                name or nothing is returned.
            class_filter (type): If passed, only instance of this class are returned.
            unique (bool): If True (default is False), there must be exactly one object
                found inside this extension that matches all of the other criteria.

        Returns:
            list of (name, type): A list of the objects found at the extension path.

            If unique is True, then the list only contains a single entry and that
            entry will be directly returned.
        """

        name, ext = _try_load_module(path)

        if name_filter is not None and name != name_filter:
            return []

        found = [(name, x) for x in self._filter_subclasses(ext, class_filter)]
        found = [(name, x) for name, x in found if self._filter_nonextensions(x)]

        if not unique:
            return found

        if len(found) > 1:
            raise ArgumentError("Extension %s should have had exactly one instance of class %s, found %d" % (path, class_filter.__name__, len(found)), classes=found)
        elif len(found) == 0:
            raise ArgumentError("Extension %s had no instances of class %s" % (path, class_filter.__name__))

        return found[0]

    def _filter_nonextensions(self, obj):
        """Remove all classes marked as not extensions.

        This allows us to have a deeper hierarchy of classes than just
        one base class that is filtered by _filter_subclasses.  Any
        class can define a class propery named:

        __NO_EXTENSION__ = True

        That class will never be returned as an extension.  This is useful
        for masking out base classes for extensions that are declared in
        CoreTools and would be present in module imports but should not
        create a second entry point.
        """

        if obj.__dict__.get('__NO_EXTENSION__', False) is True:
            return False

        return True

    def _filter_subclasses(self, obj, class_filter):
        if class_filter is None:
            return [obj]

        if isinstance(obj, ModuleType):
            return [x for x in itervalues(obj.__dict__) if inspect.isclass(x) and issubclass(x, class_filter) and x != class_filter]

        if inspect.isclass(obj) and issubclass(obj, class_filter):
            return [obj]

        self._logger.warn("Found no valid extension objects in %s, sought subclasses of %s", obj, class_filter)
        return []

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

    def add_component(self, component, temporary=False):
        """Register a component with ComponentRegistry.

        Component must be a buildable object with a module_settings.json file
        that describes its name and the domain that it is part of.  By
        default, this component is saved in the permanent registry associated
        with this environment and will remain registered for future CoreTools
        invocations.

        If you only want this component to be temporarily registered during
        this program's session, you can pass temporary=True and the component
        will be stored in RAM only, not persisted to the underlying key-value
        store.

        Args:
            component (str): The path to a component that should be registered.
            temporary (bool): Optional flag to only temporarily register the
                component for the duration of this program invocation.
        """

        tile = IOTile(component)
        value = os.path.normpath(os.path.abspath(component))

        if temporary is True:
            self._component_overlays[tile.name] = value
        else:
            self.kvstore.set(tile.name, value)

    def get_component(self, component):
        if component in self._component_overlays:
            return IOTile(self._component_overlays[component])

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
            if len(domain) != 0:
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

        ComponentRegistry._component_overlays = {}

        for key in self.list_components():
            self.remove_component(key)

    def clear(self):
        """Clear all data from the registry
        """

        self.kvstore.clear()

    def list_components(self):
        """List all of the registered component names.

        This list will include all of the permanently stored components as
        well as any temporary components that were added with a temporary=True
        flag in this session.

        Returns:
            list of str: The list of component names.

            Any of these names can be passed to get_component as is to get the
            corresponding IOTile object.
        """

        overlays = list(self._component_overlays)
        items = self.kvstore.get_all()

        return overlays + [x[0] for x in items if not x[0].startswith('config:')]

    def iter_components(self):
        """Iterate over all defined components yielding IOTile objects."""

        names = self.list_components()

        for name in names:
            yield self.get_component(name)

    def list_config(self):
        """List all of the configuration variables
        """
        items = self.kvstore.get_all()
        return ["{0}={1}".format(x[0][len('config:'):], x[1])
                for x in items if x[0].startswith('config:')]

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
        with open(default_file, "r") as infile:
            data = infile.read()
            data = data.strip()

            ComponentRegistry.SetBackingStore(data)
    except IOError:
        pass


def _try_load_module(path):
    """Try to programmatically load a python module by path.

    Path should point to a python file (optionally without the .py) at the
    end.  If it ends in a :<name> then name must point to an object defined in
    the module, which is returned instead of the module itself.

    Args:
        path (str): The path of the module to load

    Returns:
        str, object: The basename of the module loaded and the requested object.
    """

    obj_name = None
    if len(path) > 2 and ':' in path[2:]:  # Don't flag windows C: type paths
        path, _, obj_name = path.rpartition(":")

    folder, basename = os.path.split(path)
    if folder == '':
        folder = './'

    if basename == '' or not os.path.exists(path):
        raise ArgumentError("Could not find python module to load extension", path=path)

    basename, ext = os.path.splitext(basename)
    if ext not in (".py", ".pyc", ""):
        raise ArgumentError("Attempted to load module is not a python package or module (.py or .pyc)", path=path)

    try:
        fileobj = None
        fileobj, pathname, description = imp.find_module(basename, [folder])

        #Don't load modules twice
        if basename in sys.modules:
            mod = sys.modules[basename]
        else:
            mod = imp.load_module(basename, fileobj, pathname, description)

        if obj_name is not None:
            if obj_name not in mod.__dict__:
                raise ArgumentError("Cannot find named object '%s' inside module '%s'" % (obj_name, basename), path=path)

            mod = mod.__dict__[obj_name]

        return (basename, mod)
    finally:
        if fileobj is not None:
            fileobj.close()


# Update our default registry backing store appropriately
_check_registry_type()
