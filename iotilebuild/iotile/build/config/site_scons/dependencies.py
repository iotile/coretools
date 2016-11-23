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
	"""

	reg = ComponentRegistry()

	if 'DEPENDENCIES' not in build_env:
		build_env['DEPENDENCIES'] = []

	dep_targets = []

	for dep in tile.dependencies:
		try:
			tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))
			tile.filter_products(dep['products'])
		except ArgumentError:
			raise BuildError("Could not find required dependency", name=module)

		build_env['DEPENDENCIES'].append(tile)

		target = os.path.join(tile.folder, 'module_settings.json')
		dep_targets.append(target)

	return dep_targets
