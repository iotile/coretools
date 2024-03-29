# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import os.path
import utilities
from iotile.build.build import ProductResolver
from iotile.core.dev.iotileobj import IOTile
import os
import datetime
import json
import pygtrie
from SCons.Environment import Environment
from SCons.Script import Copy


def create_release_settings_action(target, source, env):
    """Copy module_settings.json and add release and build information
    """

    with open(str(source[0]), "r") as fileobj:
        settings = json.load(fileobj)

    settings['release'] = True
    settings['release_date'] = datetime.datetime.utcnow().isoformat()
    settings['dependency_versions'] = {}

    #Also insert the versions of every dependency that we used to build this component
    for dep in env['TILE'].dependencies:
        tile = IOTile(os.path.join('build', 'deps', dep['unique_id']))

        settings['dependency_versions'][dep['unique_id']] = str(tile.parsed_version)

    with open(str(target[0]), "w") as fileobj:
        json.dump(settings, fileobj, indent=4)


def copy_tilebus_definitions(tile):
    destdir = os.path.join('build', 'output', 'tilebus')

    env = Environment(tools=[])
    for tbdef in tile.find_products('tilebus_definitions'):
        tbname = os.path.basename(tbdef)

        infile = tbdef
        outfile = os.path.join(destdir, tbname)
        env.Command([outfile], [infile], Copy("$TARGET", "$SOURCE"))


def copy_linker_scripts(tile):
    destdir = os.path.join('build', 'output', 'linker')

    linkers = tile.find_products('linker_script')
    env = Environment(tools=[])

    for linker in linkers:
        linkername = os.path.basename(linker)
        srcfile = os.path.join("firmware", 'linker', linkername)
        destfile = os.path.join(destdir, linkername)

        env.Command([destfile], [srcfile], Copy("$TARGET", "$SOURCE"))


def copy_include_dirs(tile):
    """Copy all include directories that this tile defines as products in build/output/include
    """

    if 'products' not in tile.settings:
        return

    incdirs = tile.settings['products'].get('include_directories', [])
    incdirs = map(lambda x: os.path.normpath(utilities.join_path(x)), incdirs)
    incdirs = sorted(incdirs, key=lambda x: len(x))

    seen_dirs = pygtrie.PrefixSet(factory=lambda: pygtrie.StringTrie(separator=os.path.sep))

    env = Environment(tools=[])

    # all include directories are relative to the firmware/src directory
    outputbase = os.path.join('build', 'output', 'include')
    inputbase = os.path.join('firmware', 'src')
    for inc in incdirs:
        if inc in seen_dirs:
            continue

        relinput = os.path.join(inputbase, inc)
        finaldir = os.path.join(outputbase, inc)

        for folder, subdirs, filenames in os.walk(relinput):
            relfolder = os.path.relpath(folder, relinput)
            for filename in filenames:
                if filename.endswith(".h"):
                    infile = os.path.join(folder, filename)
                    outfile = os.path.join(finaldir, relfolder, filename)
                    env.Command([outfile], [infile], Copy("$TARGET", "$SOURCE"))

        seen_dirs.add(inc)


def copy_extra_files(tile):
    """Copy all files listed in a copy_files and copy_products section.

    Files listed in copy_files will be copied from the specified location
    in the current component to the specified path under the output
    folder.

    Files listed in copy_products will be looked up with a ProductResolver
    and copied copied to the specified path in the output folder.  There
    is not currently a way to specify what type of product is being resolved.
    The `short_name` given must be unique across all products from this
    component and its direct dependencies.
    """

    env = Environment(tools=[])
    outputbase = os.path.join('build', 'output')

    for src, dest in tile.settings.get('copy_files', {}).items():
        outputfile = os.path.join(outputbase, dest)
        env.Command([outputfile], [src], Copy("$TARGET", "$SOURCE"))

    resolver = ProductResolver.Create()
    for src, dest in tile.settings.get('copy_products', {}).items():
        prod = resolver.find_unique(None, src)
        outputfile = os.path.join(outputbase, dest)

        env.Command([outputfile], [prod.full_path], Copy("$TARGET", "$SOURCE"))


def copy_dependency_docs(tile):
    """Copy all documentation from dependencies into build/output/doc folder"""

    env = Environment(tools=[])

    outputbase = os.path.join('build', 'output', 'doc')
    depbase = os.path.join('build', 'deps')
    for dep in tile.dependencies:
        depdir = os.path.join(depbase, dep['unique_id'], 'doc', dep['unique_id'])
        outputdir = os.path.join(outputbase, dep['unique_id'])

        if os.path.exists(depdir):
            env.Command([outputdir], [depdir], Copy("$TARGET", "$SOURCE"))


def copy_dependency_images(tile):
    """Copy all documentation from dependencies into build/output/doc folder"""

    env = Environment(tools=[])

    outputbase = os.path.join('build', 'output')
    depbase = os.path.join('build', 'deps')
    for dep in tile.dependencies:
        depdir = os.path.join(depbase, dep['unique_id'])
        outputdir = os.path.join(outputbase)

        deptile = IOTile(depdir)

        for image in deptile.find_products('firmware_image'):
            name = os.path.basename(image)
            input_path = os.path.join(depdir, name)
            output_path = os.path.join(outputdir, name)
            env.Command([output_path], [input_path], Copy("$TARGET", "$SOURCE"))
