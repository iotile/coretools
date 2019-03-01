# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import itertools
from collections import namedtuple
from string import Template
import json
import os.path
import sys

from iotile.core.exceptions import DataError, ExternalError
from .semver import SemanticVersion, SemanticVersionRange

ReleaseStep = namedtuple('ReleaseStep', ['provider', 'args'])
ReleaseInfo = namedtuple('ReleaseInfo', ['release_date', 'dependency_versions'])
TileInfo = namedtuple('TileInfo', ['module_name', 'settings', 'architectures', 'targets', 'release_data'])

_ProductDeclaration = namedtuple('_ProductDeclaration', ['dev_path', 'release_path', 'process_func'])
_ReleaseOnlyProduct = _ProductDeclaration(r"${release}/${product}", r"${release}/${product}", None)
_DevOnlyProduct = _ProductDeclaration(r"${module}/${product}", r"${module}/${product}", None)


class IOTile(object):
    """Object representing an IOTile component that implements or extends CoreTools.

    IOTile components are "projects" in the sense of traditional IDEs,
    "packages" in nodejs or "distributions" in python.  They are single
    directories that contain related code and a metadata file that describes
    what the project is and how to use it.

    Since IOTile components describe building blocks for IOT devies, they do not
    contain code in a single language but could describe a variety of different
    kinds of artifacts such as:

    - firmware images
    - python extensions for CoreTools
    - build automation steps used in hardware manufacturing
    - emulators for specific IOTile devices

    The unifying concepts that extend to all of the above finds of components are
    that they product "artifacts" through a build process, the entire component
    has a single version and it can have dependencies on other components.

    There is a single file inside the root of the component directory,
    `module_settings.json` that contains all of this metadata.

    The `IOTile` object is constructed from a `module_settings.json` file and
    provides helper routines to parse and search its contents.

    Args:
        folder (str): The path to a folder containing a `module_settings.json`
            file that will be loaded into this IOTile object.
    """

    V1_FORMAT = "v1"
    V2_FORMAT = "v2"

    PYTHON_PRODUCTS = frozenset([
        "build_step",
        "app_module",
        "proxy_module",
        "type_package",
        "proxy_plugin",
        "virtual_tile",
        "emulated_tile",
        "virtual_device",
    ])
    """The canonical list of all product types that contain python code.

    This is used to know if this IOTile component will contain a support
    wheel, which happens if it produces any products of these types.
    """

    LIST_PRODUCTS = frozenset([
        "include_directories",
        "tilebus_definitions"
    ])
    """The canonical list of products that are stored as a list.

    Most products are stored in module_settings.json in the products map where
    the key is the path to the product and the value is the type of product.
    Some products, those in this property, are stored where the key is the
    type of product and all of the specific products are stored in a single
    list under that key.
    """

    PATH_PRODUCTS = {
        "include_directories": _ProductDeclaration(r"${release}/include/${product}", r"${release}/include/${product}",
                                                   None),
        "tilebus_definitions": _ProductDeclaration(r"${module}/firmware/src/${raw_product}",
                                                   r"${release}/tilebus/${product}", os.path.basename),
        "linker_script": _ProductDeclaration(r"${release}/linker/${product}", r"${release}/linker/${product}", None),
        "type_package": _DevOnlyProduct,
        "build_step": _DevOnlyProduct,
        "app_module": _DevOnlyProduct,
        "proxy_module": _DevOnlyProduct,
        "proxy_plugin": _DevOnlyProduct,
        "virtual_tile": _DevOnlyProduct,
        "emulated_tile": _DevOnlyProduct,
        "virtual_device": _DevOnlyProduct,
        "support_package": _DevOnlyProduct,
        "firmware_image": _ReleaseOnlyProduct,
    }
    """Declarations for products that require special path processing."""

    def __init__(self, folder):
        self.folder = folder
        self.filter_prods = False

        modfile = os.path.join(self.folder, 'module_settings.json')

        try:
            with open(modfile, "r") as infile:
                settings = json.load(infile)
        except IOError:
            raise ExternalError("Could not load module_settings.json file, "
                                "make sure this directory is an IOTile component", path=self.folder)

        file_format = settings.get('file_format', IOTile.V1_FORMAT)
        if file_format == IOTile.V1_FORMAT:
            info = self._find_v1_settings(settings)
        elif file_format == IOTile.V2_FORMAT:
            info = self._find_v2_settings(settings)
        else:
            raise DataError("Unknown file format in module_settings.json", format=file_format, path=modfile)

        self._load_settings(info)

    def _find_v1_settings(self, settings):
        """Parse a v1 module_settings.json file.

        V1 is the older file format that requires a modules dictionary with a
        module_name and modules key that could in theory hold information on
        multiple modules in a single directory.
        """

        if 'module_name' in settings:
            modname = settings['module_name']
        if 'modules' not in settings or len(settings['modules']) == 0:
            raise DataError("No modules defined in module_settings.json file")
        elif len(settings['modules']) > 1:
            raise DataError("Multiple modules defined in module_settings.json file",
                            modules=[x for x in settings['modules']])
        else:
            modname = list(settings['modules'])[0]

        if modname not in settings['modules']:
            raise DataError("Module name does not correspond with an entry in the modules directory",
                            name=modname, modules=[x for x in settings['modules']])

        release_info = self._load_release_info(settings)
        modsettings = settings['modules'][modname]
        architectures = settings.get('architectures', {})

        target_defs = settings.get('module_targets', {})
        targets = target_defs.get(modname, [])

        return TileInfo(modname, modsettings, architectures, targets, release_info)

    @classmethod
    def _load_release_info(cls, settings):
        if settings.get('release', False) is False:
            return None

        if 'release_date' not in settings:
            raise DataError("Release mode IOTile component did not include a release date")

        import dateutil.parser
        release_date = dateutil.parser.parse(settings['release_date'])
        dependency_versions = {x: SemanticVersion.FromString(y)
                               for x, y in settings.get('dependency_versions', {}).items()}

        return ReleaseInfo(release_date, dependency_versions)

    def _find_v2_settings(self, settings):
        archs = settings.get('architectures', {})
        mod_name = settings.get('module_name')
        release_info = self._load_release_info(settings)

        targets = settings.get('targets', [])

        return TileInfo(mod_name, settings, archs, targets, release_info)

    def _load_settings(self, info):
        """Load settings for a module."""

        modname, modsettings, architectures, targets, release_info = info
        self.settings = modsettings

        # Name is converted to all lowercase to canonicalize it
        prepend = ''
        if 'domain' in modsettings:
            prepend = modsettings['domain'].lower() + '/'

        key = prepend + modname.lower()

        # Copy over some key properties that we want easy access to
        self.name = key
        self.unique_id = key.replace('/', '_')
        self.short_name = modname
        self.targets = targets

        self.full_name = "Undefined"
        if "full_name" in self.settings:
            self.full_name = self.settings['full_name']

        # FIXME: make sure this is a list
        self.authors = []
        if "authors" in self.settings:
            self.authors = self.settings['authors']

        self.version = "0.0.0"
        if "version" in self.settings:
            self.version = self.settings['version']

        self.parsed_version = SemanticVersion.FromString(self.version)

        # Load all of the build products that can be created by this IOTile
        self.products = modsettings.get('products', {})

        # Load in the release information telling us how to release this component
        release_steps = modsettings.get('release_steps', [])
        self.release_steps = []
        self.can_release = False

        for step in release_steps:
            if 'provider' not in step:
                raise DataError("Invalid release step that did not have a provider key", step=step)

            parsed_step = ReleaseStep(provider=step['provider'], args=step.get('args', {}))
            self.release_steps.append(parsed_step)

        if len(self.release_steps) > 0:
            self.can_release = True

        self.dependency_versions = {}

        # If this is a release IOTile component, check for release information
        if release_info is not None:
            self.release = True
            self.release_date = release_info.release_date
            self.output_folder = self.folder
            self.dependency_versions = release_info.dependency_versions
        else:
            self.release = False
            self.output_folder = os.path.join(self.folder, 'build', 'output')

            # If this tile is a development tile and it has been built at least one, add in a release date
            # from the last time it was built
            if os.path.exists(os.path.join(self.output_folder, 'module_settings.json')):
                release_settings = os.path.join(self.output_folder, 'module_settings.json')

                with open(release_settings, 'r') as infile:
                    release_dict = json.load(infile)

                import dateutil.parser
                self.release_date = dateutil.parser.parse(release_dict['release_date'])
            else:
                self.release_date = None

        # Find all of the things that this module could possibly depend on
        # Dependencies include those defined in the module itself as well as
        # those defined in architectures that are present in the module_settings.json
        # file.
        self.dependencies = []

        archs_with_deps = [y['depends'].items() for _x, y in architectures.items() if 'depends' in y]
        if 'depends' in self.settings:
            if not isinstance(self.settings['depends'], dict):
                raise DataError("module must have a depends key that is a dictionary",
                                found=str(self.settings['depends']))

            archs_with_deps.append(self.settings['depends'].items())

        # Find all python package needed
        self.support_wheel_depends = []

        if 'python_depends' in self.settings:
            if not isinstance(self.settings['python_depends'], list):
                raise DataError("module must have a python_depends key that is a list of strings",
                                found=str(self.settings['python_depends']))

            for python_depend in self.settings['python_depends']:
                if not isinstance(python_depend, str):
                    raise DataError("module must have a python_depends key that is a list of strings",
                                    found=str(self.settings['python_depends']))

                self.support_wheel_depends.append(python_depend)

        # Also search through overlays to architectures that are defined in this module_settings.json file
        # and see if those overlays contain dependencies.
        for overlay_arch in self.settings.get('overlays', {}).values():
            if 'depends' in overlay_arch:
                archs_with_deps.append(overlay_arch['depends'].items())

        found_deps = set()
        for dep, _ in itertools.chain(*archs_with_deps):
            name, _, version = dep.partition(',')
            unique_id = name.lower().replace('/', '_')

            version = version.strip()
            if version == '':
                version = "*"

            ver_range = SemanticVersionRange.FromString(version)

            depdict = {
                'name': name,
                'unique_id': unique_id,
                'required_version': ver_range,
                'required_version_string': version
            }

            if name not in found_deps:
                self.dependencies.append(depdict)

            found_deps.add(name)

        # Store any architectures that we find in this json file for future reference
        self.architectures = architectures

        # Setup our support package information
        self.support_distribution = "iotile_support_{0}_{1}".format(self.short_name, self.parsed_version.major)

        if 'python_universal' in self.settings:
            py_version = "py2.py3"
        elif sys.version_info[0] >= 3:
            py_version = "py3"
        else:
            py_version = "py2"

        self.support_wheel = "{0}-{1}-{2}-none-any.whl".format(self.support_distribution,
                                                               self.parsed_version.pep440_string(),
                                                               py_version)
        self.has_wheel = self._check_has_wheel()

    def _check_has_wheel(self):
        for prod in self.PYTHON_PRODUCTS:
            if len(self.find_products(prod)) > 0:
                return True

        return False

    @classmethod
    def _ensure_product_string(cls, product):
        """Ensure that all product locations are strings.

        Older components specify paths as lists of path components.  Join
        those paths into a normal path string.
        """

        if isinstance(product, str):
            return product

        if isinstance(product, list):
            return os.path.join(*product)

        raise DataError("Unknown object (not str or list) specified as a component product", product=product)

    def _process_product_path(self, product, declaration):
        processed = product
        if declaration.process_func is not None:
            processed = declaration.process_func(product)

        if self.release:
            base = Template(declaration.release_path)
        else:
            base = Template(declaration.dev_path)

        path_string = base.substitute(module=self.folder, release=self.output_folder,
                                      raw_product=product, product=processed)
        return os.path.normpath(path_string)

    def find_products(self, product_type):
        """Search for products of a given type.

        Search through the products declared by this IOTile component and
        return only those matching the given type.  If the product is described
        by the path to a file, a complete normalized path will be returned.
        The path could be different depending on whether this IOTile component
        is in development or release mode.

        The behavior of this function when filter_products has been called is
        slightly different based on whether product_type is in LIST_PRODUCTS
        or not.  If product type is in LIST_PRODUCTS, then all matching
        products are returned if product_type itself was passed.  So to get
        all tilebus_definitions you would call
        ``filter_products('tilebus_definitions')``

        By contrast, other products are filtered product-by-product.  So there
        is no way to filter and get **all libraries**.  Instead you pass the
        specific product names of the libraries that you want to
        ``filter_products`` and those specific libraries are returned.
        Passing the literal string ``library`` to ``filter_products`` will not
        return only the libraries, it will return nothing since no library is
        named ``library``.

        Args:
            product_type (str): The type of product that we wish to return.

        Returns:
            list of str: The list of all products of the given type.

            If no such products are found, an empty list will be returned.
            If filter_products() has been called and the filter does not include
            this product type, an empty list will be returned.
        """

        if self.filter_prods and product_type in self.LIST_PRODUCTS and product_type not in self.desired_prods:
            return []

        if product_type in self.LIST_PRODUCTS:
            found_products = self.products.get(product_type, [])
        else:
            found_products = [x[0] for x in self.products.items()
                              if x[1] == product_type and (not self.filter_prods or x[0] in self.desired_prods)]

        found_products = [self._ensure_product_string(x) for x in found_products]

        declaration = self.PATH_PRODUCTS.get(product_type)
        if declaration is not None:
            found_products = [self._process_product_path(x, declaration) for x in found_products]

        return found_products

    def library_directories(self):
        """Return a list of directories containing any static libraries built by this IOTile."""

        libs = self.find_products('library')

        if len(libs) > 0:
            return [os.path.join(self.output_folder)]

        return []

    def filter_products(self, desired_prods):
        """When asked for a product, filter only those on this list."""

        self.filter_prods = True
        self.desired_prods = set(desired_prods)

    def path(self):
        """The path to this component."""
        return self.folder
