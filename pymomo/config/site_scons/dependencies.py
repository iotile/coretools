from pymomo.exceptions import *
import pymomo
from pymomo.dev.registry import ComponentRegistry
from SCons.Environment import Environment
import os

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
		target = os.path.join(build_env['BUILD_DIR'], "__virtual__target__" + module.replace('/', '_'))
		targets = env.Command(target, [], action=env.Action(build_dependency, "Checking dependency %s" % tile.name))

		build_env['DEPENDENCIES'].append(tile)
		dep_targets.append(target)

	return dep_targets