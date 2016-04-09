from pymomo.utilities.typedargs.annotate import *
from pymomo.utilities import typedargs
from pymomo.utilities.kvstore import KeyValueStore
from pymomo.exceptions import *
import json
import os.path
from pymomo.utilities.build import ChipFamily, build_other

@context()
class IOTile:
	"""
	IOTile

	A python representation of an IOTile module allowing you to programmatically build
	it, inspect the products that its build produces and include it as a dependency
	in another build process. 
	"""

	@param("folder", "path", "exists", desc="Path to this IOTile")
	def __init__(self, folder):
		self.folder = folder
		self.filter_prods = False

		self._load_settings()

	def _load_settings(self):
		modfile = os.path.join(self.folder, 'module_settings.json')

		with open(modfile, "r") as f:
			settings = json.load(f)

		#Figure out the modules name
		if 'modules' not in settings or len(settings['modules']) == 0:
			raise DataError("No modules defined in module_settings.json file")
		elif len(settings['modules']) > 1:
			raise DataError("Mulitple modules defined in module_settings.json file", modules=settings['modules'].keys())

		modname = settings['modules'].keys()[0]
		modsettings = settings['modules'][modname]

		prepend = ''
		if 'domain' in modsettings:
			prepend = modsettings['domain'].lower() + '/'

		key = prepend + modname

		self.name = key

		#Load all of the build products that can be created by this IOTile
		self.products = modsettings.get('products', {})

	@return_type("list(string)")
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

	@return_type("list(string)")
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

	@return_type("list(string)")
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

	@return_type("string")
	def path(self):
		return self.folder

	@annotated
	def build(self, artifacts=[]):
		"""
		Build all products in this IOTile 
		"""

		#If there's no SConstruct then there's nothing to build
		buildfile = os.path.join(self.folder, 'SConstruct')
		if not os.path.exists(buildfile):
			return

		retval, stdout, stderr = build_other(self.folder)
		if retval != 0:
			print '*** START BUILD ERROR OUTPUT ***'
			print stderr
			print '*** END BUILD ERROR OUTPUT ***'

			raise BuildError('Error building IOTile', name=self.name, path=self.folder)
