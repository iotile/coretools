# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import os.path
import sys
import logging
import imp
import inspect
import json
from types import ModuleType

import entrypoints

from iotile.core.utilities.kvstore_sqlite import SQLiteKVStore
from iotile.core.utilities.kvstore_json import JSONKVStore
from iotile.core.utilities.kvstore_mem import InMemoryKVStore
from iotile.core.exceptions import ArgumentError, ExternalError
from iotile.core.utilities.paths import settings_directory
from .iotileobj import IOTile

MISSING = object()


class ComponentRegistry:
    """ComponentRegistry

    A mapping of all of the installed components on this system that can
    be used as build dependencies and where they are located.  Also used
    to manage iotile plugins.
    """

    BackingType = SQLiteKVStore
    BackingFileName = 'component_registry.db'

    _registered_extensions = {}
    _component_overlays = {}
    _frozen_extensions = None

    def __init__(self):
        self._kvstore = None
        self._plugins = None
        self._logger = logging.getLogger(__name__)

    @property
    def frozen(self):
        """Return whether we have a cached list of all installed entry_points."""

        frozen_path = os.path.join(_registry_folder(), 'frozen_extensions.json')
        return os.path.isfile(frozen_path)

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
            self._plugins = {}

            for _, plugin in self.load_extensions('iotile.plugin'):
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

        if product_name is not None:
            for comp in self.iter_components():
                if comp_filter is not None and comp.name != comp_filter:
                    continue

                products = comp.find_products(product_name)
                for product in products:
                    try:
                        entries = self.load_extension(product, name_filter=name_filter, class_filter=class_filter,
                                                      component=comp)
                        if len(entries) == 0 and name_filter is None:
                            # Don't warn if we're filtering by name since most extensions won't match
                            self._logger.warning("Found no valid extensions in product %s of component %s",
                                              product, comp.path)
                            continue

                        found_extensions.extend(entries)
                    except:  # pylint:disable=bare-except;We don't want a broken extension to take down the whole system
                        self._logger.exception("Unable to load extension %s from local component %s at path %s",
                                               product_name, comp, product)

        for entry in self._iter_entrypoint_group(group):
            name = entry.name

            if name_filter is not None and name != name_filter:
                continue

            try:
                ext = entry.load()
            except:  # pylint:disable=bare-except;
                self._logger.warning("Unable to load %s from %s", entry.name, entry.distro, exc_info=True)
                continue

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

        if isinstance(extension, str):
            name, extension = self.load_extension(extension)[0]

        if group not in self._registered_extensions:
            self._registered_extensions[group] = []

        self._registered_extensions[group].append((name, extension))

    def clear_extensions(self, group=None):
        """Clear all previously registered extensions."""

        if group is None:
            ComponentRegistry._registered_extensions = {}
            return

        if group in self._registered_extensions:
            self._registered_extensions[group] = []

    def freeze_extensions(self):
        """Freeze the set of extensions into a single file.

        Freezing extensions can speed up the extension loading process on
        machines with slow file systems since it requires only a single file
        to store all of the extensions.

        Calling this method will save a file into the current virtual
        environment that stores a list of all currently found extensions that
        have been installed as entry_points.  Future calls to
        `load_extensions` will only search the one single file containing
        frozen extensions rather than enumerating all installed distributions.
        """

        output_path = os.path.join(_registry_folder(), 'frozen_extensions.json')

        with open(output_path, "w") as outfile:
            json.dump(self._dump_extensions(), outfile)

    def unfreeze_extensions(self):
        """Remove a previously frozen list of extensions."""

        output_path = os.path.join(_registry_folder(), 'frozen_extensions.json')
        if not os.path.isfile(output_path):
            raise ExternalError("There is no frozen extension list")

        os.remove(output_path)
        ComponentRegistry._frozen_extensions = None

    def load_extension(self, path, name_filter=None, class_filter=None, unique=False, component=None):
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
            component (IOTile): The component that this extension comes from if it is
                loaded from an installed component.  This is used to properly import
                the extension as a submodule of the component's support package.

        Returns:
            list of (name, type): A list of the objects found at the extension path.

            If unique is True, then the list only contains a single entry and that
            entry will be directly returned.
        """

        import_name = None
        if component is not None:
            import_name = _ensure_package_loaded(path, component)

        name, ext = _try_load_module(path, import_name=import_name)

        if name_filter is not None and name != name_filter:
            return []

        found = [(name, x) for x in self._filter_subclasses(ext, class_filter)]
        found = [(name, x) for name, x in found if self._filter_nonextensions(x)]

        if not unique:
            return found

        if len(found) > 1:
            raise ArgumentError("Extension %s should have had exactly one instance of class %s, found %d"
                                % (path, class_filter.__name__, len(found)), classes=found)
        elif len(found) == 0:
            raise ArgumentError("Extension %s had no instances of class %s" % (path, class_filter.__name__))

        return found[0]

    def _load_frozen_extensions(self):
        self._logger.critical("Loading frozen extensions from file, new extensions will not be found")

        frozen_path = os.path.join(_registry_folder(), 'frozen_extensions.json')
        with open(frozen_path, "r") as infile:
            extensions = json.load(infile)

        ComponentRegistry._frozen_extensions = {}
        for group in extensions:
            ComponentRegistry._frozen_extensions[group] = []

            for ext_info in extensions.get(group, []):
                name = ext_info['name']
                obj_path = ext_info['object']
                distro_info = ext_info['distribution']

                distro = None
                if distro_info is not None:
                    distro = entrypoints.Distribution(*distro_info)

                entry = entrypoints.EntryPoint.from_string(obj_path, name, distro=distro)
                ComponentRegistry._frozen_extensions[group].append(entry)

    def _iter_entrypoint_group(self, group):
        if not self.frozen:
            return entrypoints.get_group_all(group)

        if self._frozen_extensions is None:
            self._load_frozen_extensions()

        return self._frozen_extensions.get(group, [])

    @classmethod
    def _filter_nonextensions(cls, obj):
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

        # Not all objects have __dict__ attributes.  For example, tuples don't.
        # and tuples are used in iotile.build for some entry points.
        if hasattr(obj, '__dict__') and obj.__dict__.get('__NO_EXTENSION__', False) is True:
            return False

        return True

    @classmethod
    def _dump_extensions(cls, prefix="iotile."):
        extensions = {}

        for config, distro in entrypoints.iter_files_distros():
            if distro is None:
                distro_info = None
            else:
                distro_info = (distro.name, distro.version)

            for group in config:
                if prefix is not None and not group.startswith(prefix):
                    continue

                if group not in extensions:
                    extensions[group] = []

                for name, epstr in config[group].items():
                    extensions[group].append(dict(name=name, object=epstr, distribution=distro_info))

        return extensions

    def _filter_subclasses(self, obj, class_filter):
        if class_filter is None:
            return [obj]

        if isinstance(obj, ModuleType):
            return [x for x in obj.__dict__.values() if inspect.isclass(x)
                    and issubclass(x, class_filter) and x != class_filter]

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


def _registry_folder(folder=None):
    if folder is None:
        folder = settings_directory()

        # If we are relative to a virtual environment, place the registry into that virtual env
        # Support both virtualenv and pythnon 3 venv
        if hasattr(sys, 'real_prefix'):
            folder = sys.prefix
        elif hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix:
            folder = sys.prefix

    return folder


def _check_registry_type(folder=None):
    """Check if the user has placed a registry_type.txt file to choose the registry type

    If a default registry type file is found, the DefaultBackingType and DefaultBackingFile
    class parameters in ComponentRegistry are updated accordingly.

    Args:
        folder (string): The folder that we should check for a default registry type
    """

    folder = _registry_folder(folder)

    default_file = os.path.join(folder, 'registry_type.txt')

    try:
        with open(default_file, "r") as infile:
            data = infile.read()
            data = data.strip()

            ComponentRegistry.SetBackingStore(data)
    except IOError:
        pass


def _ensure_package_loaded(path, component):
    """Ensure that the given module is loaded as a submodule.

    Returns:
        str: The name that the module should be imported as.
    """

    logger = logging.getLogger(__name__)

    packages = component.find_products('support_package')
    if len(packages) == 0:
        return None
    elif len(packages) > 1:
        raise ExternalError("Component had multiple products declared as 'support_package", products=packages)

    if len(path) > 2 and ':' in path[2:]:  # Don't flag windows C: type paths
        path, _, _ = path.rpartition(":")

    package_base = packages[0]
    relative_path = os.path.normpath(os.path.relpath(path, start=package_base))
    if relative_path.startswith('..'):
        raise ExternalError("Component had python product output of support_package",
                            package=package_base, product=path, relative_path=relative_path)

    if not relative_path.endswith('.py'):
        raise ExternalError("Python product did not end with .py", path=path)

    relative_path = relative_path[:-3]
    if os.pathsep in relative_path:
        raise ExternalError("Python support wheels with multiple subpackages not yet supported",
                            relative_path=relative_path)

    support_distro = component.support_distribution
    if support_distro not in sys.modules:
        logger.debug("Creating dynamic support wheel package: %s", support_distro)
        file, path, desc = imp.find_module(os.path.basename(package_base), [os.path.dirname(package_base)])
        imp.load_module(support_distro, file, path, desc)

    return "{}.{}".format(support_distro, relative_path)


def _try_load_module(path, import_name=None):
    """Try to programmatically load a python module by path.

    Path should point to a python file (optionally without the .py) at the
    end.  If it ends in a :<name> then name must point to an object defined in
    the module, which is returned instead of the module itself.

    Args:
        path (str): The path of the module to load
        import_name (str): The explicity name that the module should be given.
            If not specified, this defaults to being the basename() of
            path.  However, if the module is inside of a support package,
            you should pass the correct name so that relative imports
            proceed correctly.

    Returns:
        str, object: The basename of the module loaded and the requested object.
    """

    logger = logging.getLogger(__name__)

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

    if import_name is None:
        import_name = basename
    else:
        logger.debug("Importing module as subpackage: %s", import_name)

    try:
        fileobj = None
        fileobj, pathname, description = imp.find_module(basename, [folder])

        # Don't load modules twice
        if basename in sys.modules:
            mod = sys.modules[basename]
        else:
            mod = imp.load_module(import_name, fileobj, pathname, description)

        if obj_name is not None:
            if obj_name not in mod.__dict__:
                raise ArgumentError("Cannot find named object '%s' inside module '%s'" % (obj_name, basename), path=path)

            mod = mod.__dict__[obj_name]

        return basename, mod
    finally:
        if fileobj is not None:
            fileobj.close()


# Update our default registry backing store appropriately
_check_registry_type()
