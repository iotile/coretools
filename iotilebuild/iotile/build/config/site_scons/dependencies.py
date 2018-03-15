# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import os
from iotile.core.exceptions import BuildError, ArgumentError
from iotile.core.dev.iotileobj import IOTile
from SCons.Environment import Environment


def load_dependencies(orig_tile, build_env):
    """Load all tile dependencies and filter only the products from each that we use

    build_env must define the architecture that we are targeting so that we get the
    correct dependency list and products per dependency since that may change
    when building for different architectures
    """

    if 'DEPENDENCIES' not in build_env:
        build_env['DEPENDENCIES'] = []

    dep_targets = []
    chip = build_env['ARCH']
    raw_arch_deps = chip.property('depends')

    #Properly separate out the version information from the name of the dependency
    #The raw keys come back as name,version
    arch_deps = {}
    for key, value in raw_arch_deps.iteritems():
        name, _, _ = key.partition(',')
        arch_deps[name] = value

    for dep in orig_tile.dependencies:
        try:
            tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))

            #Make sure we filter products using the view of module dependency products
            #as seen in the target we are targeting.
            if dep['name'] not in arch_deps:
                tile.filter_products([])
            else:
                tile.filter_products(arch_deps[dep['name']])
        except (ArgumentError, EnvironmentError):
            raise BuildError("Could not find required dependency", name=dep['name'])

        build_env['DEPENDENCIES'].append(tile)

        target = os.path.join(tile.folder, 'module_settings.json')
        dep_targets.append(target)

    return dep_targets


def _iter_dependencies(tile):
    for dep in tile.dependencies:
        try:
            yield IOTile(os.path.join('build', 'deps', dep['unique_id']))
        except (ArgumentError, EnvironmentError):
            raise BuildError("Could not find required dependency", name=dep['name'])


def find_dependency_wheels(tile):
    """Return a list of all python wheel objects created by dependencies of this tile

    Args:
        tile (IOTile): Tile that we should scan for dependencies

    Returns:
        list: A list of paths to dependency wheels
    """

    return [os.path.join(x.folder, 'python', x.support_wheel) for x in _iter_dependencies(tile) if x.has_wheel]
