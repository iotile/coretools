# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotilecore.exceptions import *
import iotilecore
from iotilebuild.build.build import build_iotile
from iotilecore.dev.registry import ComponentRegistry
from SCons.Environment import Environment
import os

def build_dependency(target, source, env):
	build_iotile(env['TILE'])

def build_dependencies(dep_dict, build_env):
	reg = ComponentRegistry()

	dep_targets = []
	if 'DEPENDENCIES' not in build_env:
		build_env['DEPENDENCIES'] = []

	for module, products in dep_dict.iteritems():
		try:
			tile = reg.find_component(module)
			tile.filter_products(products)
		except ArgumentError:
			raise BuildError("Could not find required dependency", name=module)

		env = Environment(tools=[])
		env['TILE'] = tile
		target = os.path.join(build_env['BUILD_DIR'], "__virtual__target__" + module.replace('/', '_'))
		targets = env.Command(target, [], action=env.Action(build_dependency, "Checking dependency %s" % tile.name))

		build_env['DEPENDENCIES'].append(tile)
		dep_targets.append(target)

	return dep_targets
