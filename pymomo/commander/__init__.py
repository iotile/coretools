import pymomo.utilities.typedargs
import os.path

folder = os.path.dirname(__file__)
pathname = os.path.join(folder, 'basic_types')

pymomo.utilities.typedargs.type_system.load_external_types(pathname)

# Find all of the registered IOTile components and see if we need to add any type libraries for them
from pymomo.dev.registry import ComponentRegistry

reg = ComponentRegistry()
modules = reg.list()

typelibs = reduce(lambda x,y: x+y, [reg.find(x).type_packages() for x in modules], [])
for lib in typelibs:
	if lib.endswith('.py'):
		lib = lib[:-2]

	pymomo.utilities.typedargs.type_system.load_external_types(lib)
