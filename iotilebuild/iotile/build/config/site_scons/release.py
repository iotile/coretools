# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from SCons.Script import *
from SCons.Environment import Environment
import sys
import os.path
import utilities
import struct
from iotile.core.exceptions import BuildError
from iotile.core.dev.iotileobj import IOTile
import os
import datetime
import json
import pygtrie

def create_release_settings_action(target, source, env):
    """Copy module_settings.json and add release and build information
    """

    with open(str(source[0]), "rb") as fileobj:
        settings = json.load(fileobj)

    settings['release'] = True
    settings['release_date'] = datetime.datetime.utcnow().isoformat()

    with open(str(target[0]), "wb") as fileobj:
        json.dump(settings, fileobj, indent=4)

def copy_tilebus_definitions(tile):
    destdir = os.path.join('build', 'output', 'tilebus')

    env = Environment(tools=[])
    for tbdef in tile.tilebus_definitions():
        tbname = os.path.basename(tbdef)

        infile = tbdef
        outfile = os.path.join(destdir, tbname)
        env.Command([outfile], [infile], Copy(outfile, infile))

def copy_linker_scripts(tile):
    destdir = os.path.join('build', 'output', 'linker')

    linkers = tile.linker_scripts()
    env = Environment(tools=[])
    
    for linker in linkers:
        linkername = os.path.basename(linker)
        srcfile = os.path.join("firmware", 'linker', linkername)
        destfile = os.path.join(destdir, linkername)

        env.Command([destfile], [srcfile], Copy(destfile, srcfile))

def copy_python(tile):
    """Copy all python proxy objects, type libraries and proxy plugins to build/output/python
    """

    #FIXME: Copy python files
    pass

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

    #all include directories are relative to the firmware/src directory
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
                    env.Command([outfile], [infile], Copy(outfile, infile))

        seen_dirs.add(inc)

def copy_extra_files(tile):
    """Copy all files listed in a copy_files section of the tile settings
    """

    env = Environment(tools=[])

    if 'copy_files' not in tile.settings:
        return

    outputbase = os.path.join('build', 'output')
        
    for src, dest in tile.settings['copy_files'].iteritems():
        outputfile = os.path.join(outputbase, dest)
        env.Command([outputfile], [src], Copy(outputfile, src))


def copy_dependency_docs(tile):
    """Copy all documentation from dependencies into build/output/doc folder
    """

    env = Environment(tools=[])

    outputbase = os.path.join('build', 'output', 'doc')
    depbase = os.path.join('build', 'deps')
    for dep in tile.dependencies:
        depdir = os.path.join(depbase, dep['unique_id'], 'doc', dep['unique_id'])
        outputdir = os.path.join(outputbase, dep['unique_id'])
        
        if os.path.exists(depdir):
            env.Command([outputdir], [depdir], Copy(outputdir, depdir))

def copy_dependency_images(tile):
    """Copy all documentation from dependencies into build/output/doc folder
    """

    env = Environment(tools=[])

    outputbase = os.path.join('build', 'output')
    depbase = os.path.join('build', 'deps')
    for dep in tile.dependencies:
        depdir = os.path.join(depbase, dep['unique_id'])
        outputdir = os.path.join(outputbase)

        deptile = IOTile(depdir)

        for image in deptile.firmware_images():
            name = os.path.basename(image)
            input_path = os.path.join(depdir, name)
            output_path = os.path.join(outputdir, name) 
            env.Command([output_path], [input_path], Copy(output_path, input_path))
