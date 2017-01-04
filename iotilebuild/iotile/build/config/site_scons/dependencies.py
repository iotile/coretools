# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.exceptions import *
import iotile.core
from iotile.build.build.build import build_iotile
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.dev.iotileobj import IOTile
from SCons.Environment import Environment
import os

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
        name,_,_ = key.partition(',')
        arch_deps[name] = value

    #Keep track of all of the versions of the dependencies that this tile's
    #dependencies were built with to make sure that if we use the same dep in two
    #places it has the same version.

    seen_versions = {}

    for dep in orig_tile.dependencies:
        try:
            tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))

            #Check for version conflict between a directly included dependency and a dep used to build
            #a dependency.
            if tile.unique_id in seen_versions and seen_versions[tile.unique_id][0] != tile.parsed_version:
                raise BuildError("Version conflict between direct dependency and component used to build one of our dependencies", 
                                 direct_dependency=tile.short_name, direct_version=str(tile.parsed_version), 
                                 included_version=seen_versions[tile.unique_id][0], 
                                 included_source=seen_versions[tile.unique_id][1])

            seen_versions[tile.unique_id] = (tile.parsed_version, 'direct')

            #Check for version conflicts between two included dependencies
            for inc_dep, inc_ver in tile.dependency_versions.iteritems():
                if inc_dep in seen_versions and seen_versions[inc_dep][0] != inc_ver:
                    raise BuildError("Version conflict between component used to build two of our dependencies", 
                                 component_id=inc_dep,
                                 dependency_one=tile.unique_id, version_one=str(inc_ver), 
                                 dependency_two=seen_versions[inc_dep][1], 
                                 version_two=seen_versions[inc_dep][2])

                seen_versions[inc_dep] = (inc_ver, tile.unique_id)

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

def _iter_dependencies(tile):
    for dep in tile.dependencies:
        try:
            tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))
            yield tile
        except ArgumentError:
            raise BuildError("Could not find required dependency", name=dep['name'])

def find_dependency_wheels(tile):
    """Return a list of all python wheel objects created by dependencies of this tile
    
    Args:
        tile (IOTile): Tile that we should scan for dependencies

    Returns:
        list: A list of paths to dependency wheels 
    """

    return [os.path.join(x.folder, 'python', x.support_wheel) for x in _iter_dependencies(tile) if x.has_wheel]
    