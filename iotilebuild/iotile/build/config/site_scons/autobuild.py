# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# Automatic building of firmware and unit tests using the
# scons based iotile build system

import os.path
import os
import sys
import subprocess

from SCons.Script import Action, Alias, Copy, Default,Exit, Environment

import utilities
import unit_test
import unit_test_qemu
import arm
import platform
from docbuild import *
from pythondist import *
from release import *
from iotile.core.exceptions import *
from iotile.core.dev import IOTile, ComponentRegistry
from iotile.build.build import ProductResolver
from trub_script import build_update_script, build_trub_records, combine_trub_scripts, get_sgf_checksum


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

    reg = ComponentRegistry()
    for _name, autobuild_func in reg.load_extensions('iotile.autobuild', name_filter=builder_name):
        return autobuild_func

    raise BuildError('Cannot find required autobuilder, make sure the distribution providing it is installed',
                     name=builder_name)


def autobuild_arm_library(libname):
    try:
        # Build for all targets
        family = utilities.get_family('module_settings.json')
        family.for_all_targets(family.tile.short_name, lambda x: arm.build_library(family.tile, libname, x))

        # Build all unit tests
        unit_test.build_units(os.path.join('firmware','test'), family.targets(family.tile.short_name))

        Alias('release', os.path.join('build', 'output'))
        Alias('test', os.path.join('build', 'test', 'output'))
        Default(['release', 'test'])

        autobuild_release(family)

        if os.path.exists('doc'):
            autobuild_documentation(family.tile)

    except unit_test.IOTileException as e:
        print(e.format())
        Exit(1)


def autobuild_python_test(path):
    """Add pytest unit tests to be built as part of build/test/output."""

    env = Environment(tools=[])
    target = env.Command(['build/test/output/pytest.log'], [path],
                         action=env.Action(run_pytest, "Running python unit tests"))
    env.AlwaysBuild(target)


def autobuild_python_scripts(scripts_dir):
    """Calls a list of python scripts required for the build
    
        Args:
            scripts (list(dict)): Dictionary of scripts with their arguments

            Ex.
            scripts[0] = {
                'script_path': 'example_script_1.py',
                'args': [es1_arg1, es1_arg2, es1_arg3]
            }
            scripts[1] = {
                'script_path': 'example_script_2.py',
                'args': [es2_arg1, es2_arg2]
            }
    """
 
    env = Environment(tools=[])
    script_target_output = 'build/test/output/'
    scripts_source = []
    scripts_target = []

    for script in os.listdir(scripts_dir):
        scripts_source.append(os.path.join(scripts_dir, script))
        scripts_target.append(os.path.join(script_target_output,
                                           script + '.log'))

    target = env.Command(scripts_target,
                         scripts_source,
                         action=env.Action(run_python_scripts, "Running python scripts"))
    env.AlwaysBuild(target)

def autobuild_onlycopy():
    """Autobuild a project that does not require building firmware, pcb or documentation
    """
    try:
        # Build only release information
        family = utilities.get_family('module_settings.json')
        autobuild_release(family)

        Alias('release', os.path.join('build', 'output'))
        Default(['release'])
    except unit_test.IOTileException as e:
        print(e.format())
        Exit(1)


def autobuild_docproject():
    """Autobuild a project that only contains documentation"""

    try:
        #Build only release information
        family = utilities.get_family('module_settings.json')
        autobuild_release(family)
        autobuild_documentation(family.tile)
    except unit_test.IOTileException as e:
        print(e.format())
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

    target = env.Command(['#build/output/module_settings.json'], ['#module_settings.json'],
                         action=env.Action(create_release_settings_action, "Creating release manifest"))
    env.AlwaysBuild(target)

    # Copy over release notes if they exist
    if os.path.exists('RELEASE.md'):
        env.Command(['build/output/RELEASE.md'], ['RELEASE.md'], Copy("$TARGET", "$SOURCE"))

    # Now copy across the build products that are not copied automatically
    copy_include_dirs(family.tile)
    copy_tilebus_definitions(family.tile)
    copy_dependency_docs(family.tile)
    copy_linker_scripts(family.tile)

    # Allow users to specify a hide_dependency_images flag that does not copy over all firmware images
    if not family.tile.settings.get('hide_dependency_images', False):
        copy_dependency_images(family.tile)

    copy_extra_files(family.tile)
    build_python_distribution(family.tile)

def autobuild_arm_program(elfname, test_dir=os.path.join('firmware', 'test'), patch=True, objcopy_flags=""):
    """
    Build the an ARM module for all targets and build all unit tests. If pcb files are given, also build those.
    """

    try:
        #Build for all targets
        family = utilities.get_family('module_settings.json')
        family.for_all_targets(family.tile.short_name, lambda x: arm.build_program(family.tile, elfname, x, patch=patch, objcopy_flags=objcopy_flags))

        #Build all unit tests
        unit_test.build_units(os.path.join('firmware','test'), family.targets(family.tile.short_name))

        Alias('release', os.path.join('build', 'output'))
        Alias('test', os.path.join('build', 'test', 'output'))
        Default(['release', 'test'])

        autobuild_release(family)

        if os.path.exists('doc'):
            autobuild_documentation(family.tile)

    except IOTileException as e:
        print(e.format())
        sys.exit(1)

def autobuild_doxygen(tile):
    """Generate documentation for firmware in this module using doxygen"""

    iotile = IOTile('.')

    doxydir = os.path.join('build', 'doc')
    doxyfile = os.path.join(doxydir, 'doxygen.txt')

    outfile = os.path.join(doxydir, '%s.timestamp' % tile.unique_id)
    env = Environment(ENV=os.environ, tools=[])
    env['IOTILE'] = iotile

    # There is no /dev/null on Windows
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
    """Generate documentation for this module using a combination of sphinx and breathe"""

    docdir = os.path.join('#doc')
    docfile = os.path.join(docdir, 'conf.py')
    outdir = os.path.join('build', 'output', 'doc', tile.unique_id)
    outfile = os.path.join(outdir, '%s.timestamp' % tile.unique_id)

    env = Environment(ENV=os.environ, tools=[])

    # Only build doxygen documentation if we have C firmware to build from
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


def autobuild_trub_script(file_name, slot_assignments=None, os_info=None, sensor_graph=None,
                          app_info=None, use_safeupdate=False):
    """Build a trub script that loads given firmware into the given slots.

    slot_assignments should be a list of tuples in the following form:
    ("slot X" or "controller", firmware_image_name)

    The output of this autobuild action will be a trub script in
    build/output/<file_name> that assigns the given firmware to each slot in
    the order specified in the slot_assignments list.

    Args:
        file_name (str): The name of the output file that we should create.
            This file name should end in .trub
        slot_assignments (list of (str, str)): A list of tuples containing
            the slot name and the firmware image that we should use to build
            our update script. Optional
        os_info (tuple(int, str)): A tuple of OS version tag and X.Y version
            number that will be set as part of the OTA script if included. Optional.
        sensor_graph (str): Name of sgf file. Optional.
        app_info (tuple(int, str)): A tuple of App version tag and X.Y version
            number that will be set as part of the OTA script if included. Optional.
        use_safeupdate (bool): If True, Enables safemode before the firmware update records, then
            disables them after the firmware update records.
    """

    build_update_script(file_name, slot_assignments, os_info, sensor_graph, app_info, use_safeupdate)


def autobuild_trub_records(file_name, slot_assignments=None, os_info=None, 
                           sensor_graph=None, app_info=None,
                           use_safeupdate=False):
    """Build an OTA trub script that loads given firmware into the given slots.

    slot_assignments should be a list of tuples in the following form:
    (record type, "slot X" or "controller", firmware_image_name, options)

    The output of this autobuild action will be a trub script in
    build/output/<file_name> that assigns the given firmware to each slot in
    the order specified in the slot_assignments list.

    Args:
        file_name (str): The name of the output file that we should create.
            This file name should end in .trub
        slot_assignments (list of (str, str, str, list)): A list of tuples containing
            the slot name and the firmware image that we should use to build
            our update script. Optional
        os_info (tuple(int, str)): A tuple of OS version tag and X.Y version
            number that will be set as part of the OTA script if included. Optional.
        sensor_graph (str): Name of sgf file. Optional.
        app_info (tuple(int, str)): A tuple of App version tag and X.Y version
            number that will be set as part of the OTA script if included. Optional.
        use_safeupdate (bool): If True, Enables safemode before the firmware update records, then
            disables them after the firmware update records.
    """

    build_trub_records(file_name, slot_assignments, os_info, sensor_graph, app_info, use_safeupdate)


def autobuild_combine_trub_scripts(trub_scripts_list, out_file):
    """Combines individual trub scripts into one.
    
    Args:
        trub_scripts_list (list): A list of paths to individual trub scripts.
        out_path (str): Path to save the new trub script to.
    """

    combine_trub_scripts(trub_scripts_list, out_file)


def autobuild_get_sgf_checksum(file_name, sensorgraph):
    """Returns the device checksum if it is set in one of the trub scripts"""

    return get_sgf_checksum(file_name, sensorgraph)


def autobuild_bootstrap_file(file_name, image_list):
    """Combine multiple firmware images into a single bootstrap hex file.

    The files listed in image_list must be products of either this tile or any
    dependency tile and should correspond exactly with the base name listed on
    the products section of the module_settings.json file of the corresponding
    tile.  They must be listed as firmware_image type products.

    This function keeps a global map of all of the intermediate files that it
    has had to create so that we don't try to build them multiple times.

    Args:
        file_name(str): Full name of the output bootstrap hex file.
        image_list(list of str): List of files that will be combined into a
            single hex file that will be used to flash a chip.
    """

    family = utilities.get_family('module_settings.json')
    target = family.platform_independent_target()
    resolver = ProductResolver.Create()

    env = Environment(tools=[])

    output_dir = target.build_dirs()['output']
    build_dir = target.build_dirs()['build']

    build_output_name = os.path.join(build_dir, file_name)
    full_output_name = os.path.join(output_dir, file_name)

    processed_input_images = []

    for image_name in image_list:
        image_info = resolver.find_unique('firmware_image', image_name)
        image_path = image_info.full_path

        hex_path = arm.ensure_image_is_hex(image_path)
        processed_input_images.append(hex_path)

    env.Command(build_output_name, processed_input_images,
                action=Action(arm.merge_hex_executables,
                              "Merging %d hex files into $TARGET" % len(processed_input_images)))
    env.Command(full_output_name, build_output_name, Copy("$TARGET", "$SOURCE"))
