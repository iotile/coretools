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


def build_update_script(file_name, slot_assignments, os_info=None):
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
            our update script.
        os_info (tuple(int, str)): A tuple of OS version tag and X.Y version
            number that will be set as part of the OTA script if included.
    """

    resolver = ProductResolver.Create()
    env = Environment(tools=[])

    slots = [_parse_slot(x[0]) for x in slot_assignments]
    files = [ensure_image_is_hex(resolver.find_unique("firmware_image", x[1]).full_path) for x in slot_assignments]

    env['SLOTS'] = slots
    env['OS_INFO'] = os_info
    env.Command([os.path.join('build', 'output', file_name)], files, action=Action(_build_reflash_script_action, "Building TRUB script at $TARGET"))


def _build_reflash_script_action(target, source, env):
    """Create a TRUB script containing tile and controller reflashes.

    All of the files in source must be in intel hex format. This is guaranteed
    by the ensure_image_is_hex call in build_update_script.
    """

    out_path = str(target[0])
    source = [str(x) for x in source]
    records = []

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

    os_info = env['OS_INFO']
    if os_info is not None:
        os_tag, os_version = os_info
        records.append(SetDeviceTagRecord(os_tag=os_tag, os_version=os_version))
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
