# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import itertools
from collections import namedtuple
import json
import os.path
from iotile.core.utilities.kvstore import KeyValueStore
from iotile.core.exceptions import *

class SemanticVersion(object):
    """A simple class representing a version in X.Y.Z[-prerelease] format
    """

    def __init__(self, major, minor, patch, prerelease):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = prerelease

    @classmethod
    def FromString(cls, version):
        parts = version.split('.')
        if len(parts) != 3:
            raise DataError("Invalid version format in SemanticVersion, must be X.Y.Z[-prerelease]", version=version)

        major = int(parts[0])
        minor = int(parts[1])

        if '-' in parts[2]:
            patchstr, prerelease = parts[2].split('-')
            patch = int(patchstr)
        else:
            patch = int(parts[2])
            prerelease = ""

        return SemanticVersion(major, minor, patch, prerelease)

    def __str__(self):
        version = "{0}.{1}.{2}".format(self.major, self.minor, self.patch)

        if len(self.prerelease) > 0:
            version += '-{0}'.format(self.prerelease)

        return version


ReleaseStep = namedtuple('ReleaseStep', ['provider', 'args'])


class IOTile:
    """
    IOTile

    A python representation of an IOTile module allowing you to inspect the products
    that its build produces and include it as a dependency in another build process.
    """

    def __init__(self, folder):
        self.folder = folder
        self.filter_prods = False

        self._load_settings()


    def _load_settings(self):
        modfile = os.path.join(self.folder, 'module_settings.json')

        try:
            with open(modfile, "r") as f:
                settings = json.load(f)
        except IOError:
            raise EnvironmentError("Could not load module_settings.json file, make sure this directory is an IOTile component", path=self.folder)

        if 'module_name' in settings:
            modname = settings['module_name']
        if 'modules' not in settings or len(settings['modules']) == 0:
            raise DataError("No modules defined in module_settings.json file")
        elif len(settings['modules']) > 1:
            raise DataError("Mulitple modules defined in module_settings.json file", modules=settings['modules'].keys())
        else:
            #TODO: Remove this other option once all tiles have been converted to have their own name listed out
            modname = settings['modules'].keys()[0]
        
        if modname not in settings['modules']:
            raise DataError("Module name does not correspond with an entry in the modules directory", name=modname, modules=settings['modules'].keys())
        
        modsettings = settings['modules'][modname]
        architectures = {}
        if 'architectures' in settings:
            architectures = settings['architectures']

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

        #If this is a release IOTile component, check for release information
        if 'release' in settings and settings['release'] is True:
            self.release = True

            if 'release_date' not in settings:
                raise DataError("Release mode IOTile component did not include a release date")

            import dateutil.parser
            self.release_date = dateutil.parser.parse(settings['release_date'])
            self.output_folder = self.folder
        else:
            self.release = False
            self.output_folder = os.path.join(self.folder, 'build', 'output')

            #If this tile is a development tile and it has been built at least one, add in a release date
            #from the last time it was built
            if os.path.exists(os.path.join(self.output_folder, 'module_settings.json')):
                release_settings = os.path.join(self.output_folder, 'module_settings.json')

                with open(release_settings, 'rb') as f:
                    release_dict = json.load(f)

                import dateutil.parser
                self.release_date = dateutil.parser.parse(release_dict['release_date'])
            else:
                self.release_date = None

        #Find all of the things that this module could possibly depend on
        #Dependencies include those defined in the module itself as well as
        #those defined in architectures that are present in the module_settings.json
        #file.
        self.dependencies = []

        archs_with_deps = [y['depends'].iteritems() for x,y in architectures.iteritems() if 'depends' in y]
        if 'depends' in self.settings:
            archs_with_deps.append(self.settings['depends'].iteritems())

        found_deps = set()
        for dep, _ in itertools.chain(*archs_with_deps):
            name, _, version = dep.partition(',')
            unique_id = name.lower().replace('/', '_')

            if version is '':
                version = "^0.0.0"

            depdict = {
                'name': name,
                'unique_id': unique_id,
                'required_version': version
            }

            if name not in found_deps:
                self.dependencies.append(depdict)

            found_deps.add(name)

        #Setup our support package information
        self.support_distribution = "iotile_support_{0}_{1}".format(self.short_name, self.parsed_version.major)
        self.support_wheel = "{0}-{1}-py2-none-any.whl".format(self.support_distribution, self.version)
        self.has_wheel = False

        if len(self.proxy_modules()) > 0 or len(self.proxy_plugins()) > 0 or len(self.type_packages()) > 0:
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

        libs = [x[0] for x in self.products.iteritems() if x[1] == 'library']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        badlibs = filter(lambda x: not x.startswith('lib'), libs)
        if len(badlibs) > 0:
            raise DataError("A library product was listed in a module's products without the name starting with lib", bad_libraries=badlibs)

        #Remove the prepended lib from each library name
        return [x[3:] for x in libs]

    def type_packages(self):
        """
        Return a list of the python type packages that are provided by this tile
        """

        libs = [x[0] for x in self.products.iteritems() if x[1] == 'type_package']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]

        return libs

    def linker_scripts(self):
        """
        Return a list of the linker scripts that are provided by this tile
        """

        ldscripts = [x[0] for x in self.products.iteritems() if x[1] == 'linker_script']

        if self.filter_prods:
            ldscripts = [x for x in ldscripts if x in self.desired_prods]

        # Now append the whole path so that the above comparison works based on the name of the product only
        ldscripts = [os.path.join(self.output_folder, 'linker', x) for x in ldscripts]
        return ldscripts

    def proxy_modules(self):
        """
        Return a list of the python proxy modules that are provided by this tile
        """

        libs = [x[0] for x in self.products.iteritems() if x[1] == 'proxy_module']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]
        return libs

    def proxy_plugins(self):
        """
        Return a list of the python proxy plugins that are provided by this tile
        """

        libs = [x[0] for x in self.products.iteritems() if x[1] == 'proxy_plugin']

        if self.filter_prods:
            libs = [x for x in libs if x in self.desired_prods]

        libs = [os.path.join(self.folder, x) for x in libs]
        return libs

    def firmware_images(self):
        """
        Return a list of the python proxy plugins that are provided by this tile
        """

        libs = [x[0] for x in self.products.iteritems() if x[1] == 'firmware_image']

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
