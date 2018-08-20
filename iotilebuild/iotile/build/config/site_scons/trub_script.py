"""Routines for building trub scripts."""

from __future__ import print_function, absolute_import

import os
from SCons.Script import Environment, Action
from arm import ensure_image_is_hex
from iotile.core.exceptions import BuildError
from iotile.core.hw.update import UpdateScript
from iotile.core.hw.update.records import ReflashTileRecord, ReflashControllerRecord, SetDeviceTagRecord
from iotile.build.build import ProductResolver
from iotile.core.utilities.intelhex import IntelHex
from iotile.sg.compiler import compile_sgf
from iotile.sg.output_formats.script import format_script
from iotile.core.hw.update.script import UpdateScript

def build_update_script(file_name, slot_assignments=None, os_info=None, sensor_graph=None, app_info=None):
    """Build a trub script that loads given firmware into the given slots.

    slot_assignments should be a list of tuples in the following form:
    ("slot X" or "controller", firmware_image_name)

    The output of this autobuild action will be a trub script in
    build/output/<file_name> that assigns the given firmware to each slot in
    the order specified in the slot_assigments list.

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
    """

    resolver = ProductResolver.Create()
    env = Environment(tools=[])
    files = []

    if slot_assignments is not None:
        slots = [_parse_slot(x[0]) for x in slot_assignments]
        files = [ensure_image_is_hex(resolver.find_unique("firmware_image", x[1]).full_path) for x in slot_assignments]
        env['SLOTS'] = slots
    else:
        env['SLOTS'] = None

    env['OS_INFO'] = os_info
    env['APP_INFO'] = app_info
    env['UPDATE_SENSORGRAPH'] = False

    if sensor_graph is not None:
        files.append(sensor_graph)
        env['UPDATE_SENSORGRAPH'] = True

    env.Command([os.path.join('build', 'output', file_name)], files, action=Action(_build_reflash_script_action, "Building TRUB script at $TARGET"))


def _build_reflash_script_action(target, source, env):
    """Create a TRUB script containing tile and controller reflashes and/or sensorgraph

    If the app_info is provided, then the final source file will be a sensorgraph.
    All subsequent files in source must be in intel hex format. This is guaranteed
    by the ensure_image_is_hex call in build_update_script.
    """

    out_path = str(target[0])
    source = [str(x) for x in source]
    records = []

    #Update application firmwares
    if env['SLOTS'] is not None:
        for (controller, slot_id), image_path in zip(env['SLOTS'], source):
            hex_data = IntelHex(image_path)
            hex_data.padding = 0xFF

            offset = hex_data.minaddr()
            bin_data = bytearray(hex_data.tobinarray(offset, hex_data.maxaddr()))

            if controller:
                record = ReflashControllerRecord(bin_data, offset)
            else:
                record = ReflashTileRecord(slot_id, bin_data, offset)

            records.append(record)

    #Update sensorgraph
    if env['UPDATE_SENSORGRAPH']:
        sensor_graph_file = source[-1]
        sensor_graph = compile_sgf(sensor_graph_file)
        output = format_script(sensor_graph)
        records += UpdateScript.FromBinary(output).records

    #Update App and OS Tag
    os_info = env['OS_INFO']
    app_info = env['APP_INFO']
    if os_info is not None:
        os_tag, os_version = os_info
        records.append(SetDeviceTagRecord(os_tag=os_tag, os_version=os_version))
    if app_info is not None:
        app_tag, app_version = app_info
        records.append(SetDeviceTagRecord(app_tag=app_tag, app_version=app_version))

    script = UpdateScript(records)

    with open(out_path, "wb") as outfile:
        outfile.write(script.encode())


def _parse_slot(slot):
    if slot == 'controller':
        return (True, 0)
    elif not slot.startswith('slot '):
        raise BuildError("Invalid slot specifier that was not controller|slot X, where X is an integer", slot=slot)

    try:
        slot_number = int(slot[5:], 0)
    except ValueError:
        raise BuildError("Could not convert slot number to integer", slot=slot)

    return (False, slot_number)
