# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import itertools
from collections import namedtuple
import json
import os.path
import sys
from future.utils import viewitems, itervalues
from past.builtins import basestring
from iotile.core.exceptions import DataError, ExternalError
from .semver import SemanticVersion, SemanticVersionRange

ReleaseStep = namedtuple('ReleaseStep', ['provider', 'args'])
ReleaseInfo = namedtuple('ReleaseInfo', ['release_date', 'dependency_versions'])
TileInfo = namedtuple('TileInfo', ['module_name', 'settings', 'architectures', 'targets', 'release_data'])


class IOTile(object):
    """
    IOTile

    A python representation of an IOTile module allowing you to inspect the products
    that its build produces and include it as a dependency in another build process.
    """

    V1_FORMAT = "v1"
    V2_FORMAT = "v2"

    def __init__(self, folder):
        self.folder = folder
        self.filter_prods = False

        modfile = os.path.join(self.folder, 'module_settings.json')

        try:
            with open(modfile, "r") as infile:
                settings = json.load(infile)
        except IOError:
            raise ExternalError("Could not load module_settings.json file, make sure this directory is an IOTile component", path=self.folder)

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
            raise DataError("Multiple modules defined in module_settings.json file", modules=[x for x in settings['modules']])
        else:
            modname = list(settings['modules'])[0]

        if modname not in settings['modules']:
            raise DataError("Module name does not correspond with an entry in the modules directory", name=modname, modules=[x for x in settings['modules']])

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
        dependency_versions = {x: SemanticVersion.FromString(y) for x, y in viewitems(settings.get('dependency_versions', {}))}

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

        #Name is converted to all lowercase to canonicalize it
        prepend = ''
        if 'domain' in modsettings:
            prepend = modsettings['domain'].lower() + '/'

        key = prepend + modname.lower()

        #Copy over some key properties that we want easy access to
        self.name = key
        self.unique_id = key.replace('/', '_')
        self.short_name = modname
        self.targets = targets

        self.full_name = "Undefined"
        if "full_name" in self.settings:
            self.full_name = self.settings['full_name']

        #FIXME: make sure this is a list
        self.authors = []
        if "authors" in self.settings:
            self.authors = self.settings['authors']

        self.version = "0.0.0"
        if "version" in self.settings:
            self.version = self.settings['version']

        self.parsed_version = SemanticVersion.FromString(self.version)

        #Load all of the build products that can be created by this IOTile
        self.products = modsettings.get('products', {})

        #Load in the release information telling us how to release this component
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

        #If this is a release IOTile component, check for release information
        if release_info is not None:
            self.release = True
            self.release_date = release_info.release_date
            self.output_folder = self.folder
            self.dependency_versions = release_info.dependency_versions
        else:
            self.release = False
            self.output_folder = os.path.join(self.folder, 'build', 'output')

            #If this tile is a development tile and it has been built at least one, add in a release date
            #from the last time it was built
            if os.path.exists(os.path.join(self.output_folder, 'module_settings.json')):
                release_settings = os.path.join(self.output_folder, 'module_settings.json')

                with open(release_settings, 'rb') as infile:
                    release_dict = json.load(infile)

                import dateutil.parser
                self.release_date = dateutil.parser.parse(release_dict['release_date'])
            else:
                self.release_date = None

        #Find all of the things that this module could possibly depend on
        #Dependencies include those defined in the module itself as well as
        #those defined in architectures that are present in the module_settings.json
        #file.
        self.dependencies = []

        archs_with_deps = [viewitems(y['depends']) for _x, y in viewitems(architectures) if 'depends' in y]
        if 'depends' in self.settings:
            if not isinstance(self.settings['depends'], dict):
                raise DataError("module must have a depends key that is a dictionary", found=str(self.settings['depends']))

            archs_with_deps.append(viewitems(self.settings['depends']))

        #Find all python package needed
        self.support_wheel_depends = []

        if 'python_depends' in self.settings:
            if not isinstance(self.settings['python_depends'], list):
                raise DataError("module must have a python_depends key that is a list of strings",
                                found=str(self.settings['python_depends']))

            for python_depend in self.settings['python_depends']:
                if not isinstance(python_depend, basestring):
                    raise DataError("module must have a python_depends key that is a list of strings",
                                    found=str(self.settings['python_depends']))

                self.support_wheel_depends.append(python_depend)

        #Also search through overlays to architectures that are defined in this module_settings.json file
        #and see if those overlays contain dependencies.
        for overlay_arch in itervalues(self.settings.get('overlays', {})):
            if 'depends' in overlay_arch:
                archs_with_deps.append(viewitems(overlay_arch['depends']))

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
        self.has_wheel = False

        if len(self.proxy_modules()) > 0 or len(self.proxy_plugins()) > 0 or len(self.type_packages()) > 0 or \
           len(self.app_modules()) > 0 or len(self.build_steps()) > 0:
            self.has_wheel = True

    def include_directories(self):
        """
        Return a list of all include directories that this IOTile could provide other tiles
        """

        #Only return include directories if we're returning everything or we were asked for it
        if self.filter_prods and 'include_directories' not in self.desired_prods:
            return []

        if 'include_directories' in self.products:
            if self.release:
                joined_dirs = [os.path.join(self.output_folder, 'include', *x) for x in self.products['include_directories']]
            else:
                joined_dirs = [os.path.join(self.output_folder, *x) for x in self.products['include_directories']]
            return joined_dirs

        return []

    def libraries(self):
        """
        Return a list of all libraries produced by this IOTile that could be provided to other tiles
        """

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'library']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        badlibs = [x for x in libs if not x.startswith('lib')]
        if len(badlibs) > 0:
            raise DataError("A library product was listed in a module's products without the name starting with lib", bad_libraries=badlibs)

        #Remove the prepended lib from each library name
        return [x[3:] for x in libs]

    def type_packages(self):
        """
        Return a list of the python type packages that are provided by this tile
        """

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'type_package']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]

        return libs

    def linker_scripts(self):
        """
        Return a list of the linker scripts that are provided by this tile
        """

        ldscripts = [x[0] for x in viewitems(self.products) if x[1] == 'linker_script']

        if self.filter_prods:
            ldscripts = [x for x in ldscripts if x in self.desired_prods]

        # Now append the whole path so that the above comparison works based on the name of the product only
        ldscripts = [os.path.join(self.output_folder, 'linker', x) for x in ldscripts]
        return ldscripts

    def proxy_modules(self):
        """
        Return a list of the python proxy modules that are provided by this tile
        """

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'proxy_module']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]
        return libs

    def app_modules(self):
        """Return a list of all of the python app module that are provided by this tile."""

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'app_module']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]
        return libs

    def build_steps(self):
        """Return a list of all of the python build steps that are provided by this tile."""

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'build_step']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]
        return libs

    def proxy_plugins(self):
        """
        Return a list of the python proxy plugins that are provided by this tile
        """

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'proxy_plugin']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]
        return libs

    def firmware_images(self):
        """
        Return a list of the python proxy plugins that are provided by this tile
        """

        libs = [x[0] for x in viewitems(self.products) if x[1] == 'firmware_image']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.output_folder, x) for x in libs]
        return libs

    def tilebus_definitions(self):
        """
        Return a list of all tilebus definitions that this IOTile could provide other tiles
        """

        #Only return include directories if we're returning everything or we were asked for it
        if self.filter_prods and 'tilebus_definitions' not in self.desired_prods:
            return []

        if 'tilebus_definitions' in self.products:
            if self.release:
                #For released tiles, all of the tilebus definitions are copies to the same directory
                joined_dirs = [os.path.join(self.output_folder, 'tilebus', os.path.basename(os.path.join(*x))) for x in self.products['tilebus_definitions']]
            else:
                joined_dirs = [os.path.join(self.folder, 'firmware', 'src', *x) for x in self.products['tilebus_definitions']]
            return joined_dirs

        return []

    def library_directories(self):
        libs = self.libraries()

        if len(libs) > 0:
            return [os.path.join(self.output_folder)]

        return []

    def filter_products(self, desired_prods):
        """
        When asked for a product that this iotile produces, filter only those on this list
        """

        self.filter_prods = True
        self.desired_prods = set(desired_prods)

    def path(self):
        return self.folder
