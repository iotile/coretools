from pymomo.exceptions import *
import pymomo
from pymomo.dev.registry import ComponentRegistry
from SCons.Environment import Environment

def build_dependency(target, source, env):
	env['TILE'].build()

def build_dependencies(dep_dict, build_env):
	reg = ComponentRegistry()

	dep_targets = []
	if 'DEPENDENCIES' not in build_env:
		build_env['DEPENDENCIES'] = []

	for module, products in dep_dict.iteritems():
		try:
			tile = reg.find(module)
			tile.filter_products(products)
		except ArgumentError:
			raise BuildError("Could not find required dependency", name=module)

		env = Environment()
		env['TILE'] = tile
		targets = env.Command("__virtual__target__" + module, [], action=env.Action(build_dependency, "Building dependency %s" % tile.name))

		build_env['DEPENDENCIES'].append(tile)
		dep_targets.append(targets[0])

	return dep_targets