# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotilecore.utilities.kvstore import KeyValueStore
from iotilecore.exceptions import *
import json
import os.path

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

		#Figure out the modules name
		if 'modules' not in settings or len(settings['modules']) == 0:
			raise DataError("No modules defined in module_settings.json file")
		elif len(settings['modules']) > 1:
			raise DataError("Mulitple modules defined in module_settings.json file", modules=settings['modules'].keys())

		modname = settings['modules'].keys()[0]
		modsettings = settings['modules'][modname]

		self.settings = modsettings

		#Name is converted to all lowercase to canonicalize it
		prepend = ''
		if 'domain' in modsettings:
			prepend = modsettings['domain'].lower() + '/'

		key = prepend + modname.lower()

		#Copy over some key properties that we want easy access to
		self.name = key
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

		#Load all of the build products that can be created by this IOTile
		self.products = modsettings.get('products', {})

	def include_directories(self):
		"""
		Return a list of all include directories that this IOTile could provide other tiles
		"""

		#Only return include directories if we're returning everything or we were asked for it 
		if self.filter_prods and 'include_directories' not in self.desired_prods:
			return []

		if 'include_directories' in self.products:
			joined_dirs = [os.path.join(self.folder, *x) for x in self.products['include_directories']]
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
		ldscripts = [os.path.join(self.folder, 'build', 'output', x) for x in ldscripts]
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


	def tilebus_definitions(self):
		"""
		Return a list of all tilebus definitions that this IOTile could provide other tiles
		"""

		#Only return include directories if we're returning everything or we were asked for it 
		if self.filter_prods and 'tilebus_definitions' not in self.desired_prods:
			return []

		if 'tilebus_definitions' in self.products:
			joined_dirs = [os.path.join(self.folder, *x) for x in self.products['tilebus_definitions']]
			return joined_dirs

		return []

	def library_directories(self):
		libs = self.libraries()

		if len(libs) > 0:
			return [os.path.join(self.folder, 'build', 'output')]

		return []

	def filter_products(self, desired_prods):
		"""
		When asked for a product that this iotile produces, filter only those on this list
		"""

		self.filter_prods = True
		self.desired_prods = set(desired_prods)

	def path(self):
		return self.folder
