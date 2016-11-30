# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.exceptions import *
import iotile.core
from iotile.build.build.build import build_iotile
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.dev.iotileobj import IOTile
from SCons.Environment import Environment
import os

def load_dependencies(tile, build_env):
	"""Load all tile dependencies and filter only the products from each that we use

	build_env must define the architecture that we are targeting so that we get the
	correct dependency list and products per dependency since that may change
	when building for different architectures
	"""

	reg = ComponentRegistry()

	if 'DEPENDENCIES' not in build_env:
		build_env['DEPENDENCIES'] = []

	dep_targets = []
	chip = build_env['ARCH']
	arch_deps = chip.property('depends')

	for dep in tile.dependencies:
		try:
			tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))

			#Make sure we filter products using the view of module dependency products
			#as seen in the target we are targeting.
			if dep['name'] not in arch_deps:
				tile.filter_products([])
			else:
				tile.filter_products(arch_deps[dep['name']])
		except ArgumentError:
			raise BuildError("Could not find required dependency", name=dep['name'])

		build_env['DEPENDENCIES'].append(tile)

		target = os.path.join(tile.folder, 'module_settings.json')
		dep_targets.append(target)

	return dep_targets
