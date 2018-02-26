# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# Automatic building of firmware and unit tests using the
# scons based iotile build system

import utilities
import unit_test
import unit_test_qemu
from SCons.Script import *
import os.path
import os
import sys
import itertools
import arm
import platform
from docbuild import *
from pythondist import *
from release import *
from iotile.core.exceptions import *
import iotile.core
from iotile.core.dev.iotileobj import IOTile
import pkg_resources


def require(builder_name):
    """Find an advertised autobuilder and return it

    This function searches through all installed distributions to find
    if any advertise an entry point with group 'iotile.autobuild' and
    name equal to builder_name.  The first one that is found is returned.

    This function raises a BuildError if it cannot find the required
    autobuild function

    Args:
        builder_name (string): The name of the builder to find

    Returns:
        callable: the autobuilder function found in the search
    """

    for entry in pkg_resources.iter_entry_points('iotile.autobuild'):
        if entry.name == builder_name:
            autobuild_func = entry.load()
            return autobuild_func

    raise BuildError('Cannot find required autobuilder, make sure the distribution providing it is installed', name=builder_name)

def autobuild_arm_library(libname):
    try:
        #Build for all targets
        family = utilities.get_family('module_settings.json')
        family.for_all_targets(family.tile.short_name, lambda x: arm.build_library(family.tile, libname, x))

        #Build all unit tests
        unit_test.build_units(os.path.join('firmware','test'), family.targets(family.tile.short_name))

        Alias('release', os.path.join('build', 'output'))
        Alias('test', os.path.join('build', 'test', 'output'))
        Default(['release', 'test'])

        autobuild_release(family)

        if os.path.exists('doc'):
            autobuild_documentation(family.tile)

    except unit_test.IOTileException as e:
        print e.format()
        Exit(1)

def autobuild_onlycopy():
    """Autobuild a project that does not require building firmware, pcb or documentation
    """
    try:
        #Build only release information
        family = utilities.get_family('module_settings.json')
        autobuild_release(family)

        Alias('release', os.path.join('build', 'output'))
        Default(['release'])
    except unit_test.IOTileException as e:
        print e.format()
        Exit(1)

def autobuild_docproject():
    """Autobuild a project that only contains documentation
    """

    try:
        #Build only release information
        family = utilities.get_family('module_settings.json')
        autobuild_release(family)
        autobuild_documentation(family.tile)
    except unit_test.IOTileException as e:
        print e.format()
        Exit(1)

def autobuild_release(family=None):
    """Copy necessary files into build/output so that this component can be used by others

    Args:
        family (ArchitectureGroup): The architecture group that we are targeting.  If not
            provided, it is assumed that we are building in the current directory and the
            module_settings.json file is read to create an ArchitectureGroup
    """

    if family is None:
        family = utilities.get_family('module_settings.json')

    env = Environment(tools=[])
    env['TILE'] = family.tile

    target = env.Command(['#build/output/module_settings.json'], ['#module_settings.json'], action=env.Action(create_release_settings_action, "Creating release manifest"))
    env.AlwaysBuild(target)

    #Now copy across the build products that are not copied automatically
    copy_include_dirs(family.tile)
    copy_tilebus_definitions(family.tile)
    copy_dependency_docs(family.tile)
    copy_linker_scripts(family.tile)
    copy_dependency_images(family.tile)
    copy_extra_files(family.tile)

    build_python_distribution(family.tile)

def autobuild_arm_program(elfname, test_dir=os.path.join('firmware', 'test'), patch=True):
    """
    Build the an ARM module for all targets and build all unit tests. If pcb files are given, also build those.
    """

    try:
        #Build for all targets
        family = utilities.get_family('module_settings.json')
        family.for_all_targets(family.tile.short_name, lambda x: arm.build_program(family.tile, elfname, x, patch=patch))

        #Build all unit tests
        unit_test.build_units(os.path.join('firmware','test'), family.targets(family.tile.short_name))

        Alias('release', os.path.join('build', 'output'))
        Alias('test', os.path.join('build', 'test', 'output'))
        Default(['release', 'test'])

        autobuild_release(family)

        if os.path.exists('doc'):
            autobuild_documentation(family.tile)

    except IOTileException as e:
        print e.format()
        sys.exit(1)

def autobuild_doxygen(tile):
    """
    Generate documentation for firmware in this module using doxygen
    """

    iotile = IOTile('.')

    doxydir = os.path.join('build', 'doc')
    doxyfile = os.path.join(doxydir, 'doxygen.txt')

    outfile = os.path.join(doxydir, '%s.timestamp' % tile.unique_id)
    env = Environment(ENV = os.environ)
    env['IOTILE'] = iotile

    #There is no /dev/null on Windows
    if platform.system() == 'Windows':
        action = 'doxygen %s > NUL' % doxyfile
    else:
        action = 'doxygen %s > /dev/null' % doxyfile

    Alias('doxygen', doxydir)
    env.Clean(outfile, doxydir)

    inputfile = doxygen_source_path()

    env.Command(doxyfile, inputfile, action=env.Action(lambda target, source, env: generate_doxygen_file(str(target[0]), iotile), "Creating Doxygen Config File"))
    env.Command(outfile, doxyfile, action=env.Action(action, "Building Firmware Documentation"))

def autobuild_documentation(tile):
    """
    Generate documentation for this module using a combination of sphinx and breathe
    """

    docdir = os.path.join('#doc')
    docfile = os.path.join(docdir, 'conf.py')
    outdir = os.path.join('build', 'output', 'doc', tile.unique_id)
    outfile = os.path.join(outdir, '%s.timestamp' % tile.unique_id)

    env = Environment(ENV = os.environ)

    #Only build doxygen documentation if we have C firmware to build from
    if os.path.exists('firmware'):
        autobuild_doxygen(tile)
        env.Depends(outfile, 'doxygen')

    # There is no /dev/null on Windows
    # Also disable color output on Windows since it seems to leave powershell
    # in a weird state.
    if platform.system() == 'Windows':
        action = 'sphinx-build --no-color -b html %s %s > NUL' % (docdir[1:], outdir)
    else:
        action = 'sphinx-build -b html %s %s > /dev/null' % (docdir[1:], outdir)

    env.Command(outfile, docfile, action=env.Action(action, "Building Component Documentation"))
    Alias('documentation', outdir)
    env.Clean(outfile, outdir)

def autobuild_bootstrap_file(file_name, image_list):
    """Combine multiple firmware images into a single bootstrap hex file.
    
    Args:
        file_name(str): Full name of output bootstrap hex file
        image_list(list): List of files that will be combined into a single hex file
            that will be used to flash a chip.
    """
    outputbase = os.path.join('build', 'output')
    if platform.system() == 'Windows':
        env = Environment(tools=['mingw'], ENV=os.environ)
    else:
        env = Environment(tools=['default'], ENV=os.environ)
    
    full_output_name      = os.path.join(outputbase,file_name)
    
    full_image_list_names = []
    temporary_hex_files   = []
    hex_copy_command_string = []

    for image in image_list:
        input_file = os.path.join(outputbase, image)
        root, ext = os.path.splitext(input_file)
        if len(ext) == 0:
            raise ArgumentError("Unknown file format or missing file extension", file_name=image)
        file_format = ext[1:]
        full_image_list_names.append(input_file)

        if file_format == 'hex':
            continue
        elif file_format == 'elf':
            new_file = root + '.hex'
            hex_copy_command_string += ["arm-none-eabi-objcopy -O ihex %s %s" % (input_file, new_file)]
            temporary_hex_files.append(new_file)
        else:
            raise ArgumentError("Unknown file format or file extension", file_name=input_file)
    SideEffect(temporary_hex_files, full_output_name)
    env.Command(full_output_name, full_image_list_names, 
        hex_copy_command_string + [arm.merge_hex_executables, Delete(temporary_hex_files)]
    )