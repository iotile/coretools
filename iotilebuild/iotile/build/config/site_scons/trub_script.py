"""Routines for building trub scripts."""

import os
from SCons.Script import Environment, Action
from arm import ensure_image_is_hex
from iotile.core.exceptions import BuildError
from iotile.core.hw.update.records import ReflashTileRecord, ReflashControllerRecord, EnhancedReflashControllerRecord, SetDeviceTagRecord, SendRPCRecord
from iotile.build.build import ProductResolver
from iotile.core.utilities.intelhex import IntelHex
from iotile.sg.compiler import compile_sgf
from iotile.sg.output_formats.script import format_script
from iotile.sg.update.setconfig_record import SetConfigRecord
from iotile.core.hw.update.script import UpdateScript
from iotile.core.hw.update.record import UpdateRecord


def build_update_script(file_name, slot_assignments=None, os_info=None, sensor_graph=None,
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
        use_safeupdate (bool): Enables safe firmware update
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

    env['USE_SAFEUPDATE'] = use_safeupdate
    env['OS_INFO'] = os_info
    env['APP_INFO'] = app_info
    env['UPDATE_SENSORGRAPH'] = False

    if sensor_graph is not None:
        files.append(sensor_graph)
        env['UPDATE_SENSORGRAPH'] = True

    env.Command([os.path.join('build', 'output', file_name)], files,
                action=Action(_build_reflash_script_action, "Building TRUB script at $TARGET"))


def _build_reflash_script_action(target, source, env):
    """Create a TRUB script containing tile and controller reflashes and/or sensorgraph

    If the app_info is provided, then the final source file will be a sensorgraph.
    All subsequent files in source must be in intel hex format. This is guaranteed
    by the ensure_image_is_hex call in build_update_script.
    """

    out_path = str(target[0])
    source = [str(x) for x in source]
    records = []

    if env['USE_SAFEUPDATE']:
        sgf_off = SendRPCRecord(8,0x2005,bytearray([0])) # Disable Sensorgraph
        records.append(sgf_off)
        safemode_enable = SendRPCRecord(8,0x1006,bytearray([1])) # Enable Safemode
        records.append(safemode_enable)

    # Update application firmwares
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

    # Update sensorgraph
    if env['UPDATE_SENSORGRAPH']:
        sensor_graph_file = source[-1]
        sensor_graph = compile_sgf(sensor_graph_file)
        output = format_script(sensor_graph)
        records += UpdateScript.FromBinary(output).records

    # Update App and OS Tag
    os_info = env['OS_INFO']
    app_info = env['APP_INFO']
    if os_info is not None:
        os_tag, os_version = os_info
        records.append(SetDeviceTagRecord(os_tag=os_tag, os_version=os_version))
    if app_info is not None:
        app_tag, app_version = app_info
        records.append(SetDeviceTagRecord(app_tag=app_tag, app_version=app_version))

    if env['USE_SAFEUPDATE']:
        safemode_disable = SendRPCRecord(8,0x1006,bytearray([0]))  # Disable safemode
        records.append(safemode_disable)
        sgf_on = SendRPCRecord(8,0x2005,bytearray([1]))  # Enable Sensorgraph
        records.append(sgf_on)

    script = UpdateScript(records)

    with open(out_path, "wb") as outfile:
        outfile.write(script.encode())


def _parse_slot(slot):
    if slot == 'controller':
        return True, 0
    elif not slot.startswith('slot '):
        raise BuildError("Invalid slot specifier that was not controller|slot X, where X is an integer", slot=slot)

    try:
        slot_number = int(slot[5:], 0)
    except ValueError:
        raise BuildError("Could not convert slot number to integer", slot=slot)

    return False, slot_number


def build_trub_records(file_name, slot_assignments=None, os_info=None,
                       sensor_graph=None, app_info=None,
                       use_safeupdate=False):
    """Build a trub script based on the records received for each slot.

    slot_assignments should be a list of tuples in the following form:
    ("slot X" or "controller", firmware_image_name, record_type, args)

    The output of this autobuild action will be a trub script in
    build/output/<file_name> that assigns the given firmware to each slot in
    the order specified in the slot_assignments list.

    Args:
        file_name (str): The name of the output file that we should create.
            This file name should end in .trub
        slot_assignments (list of (str, str, str, list)): The tuple contains
            (slot name, firmware file, record type, args)
        os_info (tuple(int, str)): A tuple of OS version tag and X.Y version
            number that will be set as part of the OTA script if included. Optional.
        sensor_graph (str): Name of sgf file. Optional.
        app_info (tuple(int, str)): A tuple of App version tag and X.Y version
            number that will be set as part of the OTA script if included. Optional.
        use_safeupdate (bool): Enables safe firmware update
    """

    resolver = ProductResolver.Create()
    env = Environment(tools=[])
    files = []
    records = []

    if slot_assignments is not None:
        slots = [_parse_slot_assignment(x) for x in slot_assignments]
        files = [ensure_image_is_hex(resolver.find_unique("firmware_image", x[1]).full_path) for x in slot_assignments]
        env['SLOTS'] = slots
    else:
        env['SLOTS'] = None

    env['USE_SAFEUPDATE'] = use_safeupdate
    env['OS_INFO'] = os_info
    env['APP_INFO'] = app_info
    env['UPDATE_SENSORGRAPH'] = False

    if sensor_graph is not None:
        files.append(sensor_graph)
        env['UPDATE_SENSORGRAPH'] = True

    env.Command([os.path.join('build', 'output', file_name)], files,
                action=Action(_build_records_action, "Building TRUB script at $TARGET"))


def _build_records_action(target, source, env):
    """Create a TRUB script different records for controllers and tiles

    If the app_info is provided, then the final source file will be a sensorgraph.
    All subsequent files in source must be in intel hex format. This is guaranteed
    by the ensure_image_is_hex call in build_update_script.
    """

    out_path = str(target[0])
    source = [str(x) for x in source]
    records = []

    if env['USE_SAFEUPDATE']:
        sgf_off = SendRPCRecord(8,0x2005,bytearray([0])) # Disable Sensorgraph
        records.append(sgf_off)
        safemode_enable = SendRPCRecord(8,0x1006,bytearray([1])) # Enable Safemode
        records.append(safemode_enable)

    # Update application firmwares
    if env['SLOTS'] is not None:
        for (slot_id, record_type, args), image_path in zip(env['SLOTS'], source):
            record = _build_record(slot_id, image_path, record_type, args)
            records.append(record)

    # Update sensorgraph
    if env['UPDATE_SENSORGRAPH']:
        sensor_graph_file = source[-1]
        sensor_graph = compile_sgf(sensor_graph_file)
        output = format_script(sensor_graph)
        records += UpdateScript.FromBinary(output).records

    # Update App and OS Tag
    os_info = env['OS_INFO']
    app_info = env['APP_INFO']
    if os_info is not None:
        os_tag, os_version = os_info
        records.append(SetDeviceTagRecord(os_tag=os_tag, os_version=os_version))
    if app_info is not None:
        app_tag, app_version = app_info
        records.append(SetDeviceTagRecord(app_tag=app_tag, app_version=app_version))

    if env['USE_SAFEUPDATE']:
        safemode_disable = SendRPCRecord(8,0x1006,bytearray([0]))  # Disable safemode
        records.append(safemode_disable)
        sgf_on = SendRPCRecord(8,0x2005,bytearray([1]))  # Enable Sensorgraph
        records.append(sgf_on)

    script = UpdateScript(records)

    with open(out_path, "wb") as outfile:
        outfile.write(script.encode())


def _build_record(slot_number, image_path, record_type, args):
    """Builds the appropriate record for the slot given the specified record type"""
    hex_data = IntelHex(image_path)
    hex_data.padding = 0xFF

    offset = hex_data.minaddr()
    bin_data = bytearray(hex_data.tobinarray(offset, hex_data.maxaddr()))

    if slot_number == 0: # If slot is controller
        if record_type == 2: # kReflashControllerTile
            return ReflashControllerRecord(bin_data, offset)
        elif record_type == 3: # kExecuteRPCWithoutCheck
            pass # Not implemented yet
        elif record_type == 4: # kExecuteRPCWithCheck
            pass # Not implemented yet
        elif record_type == 5: # kResetController
            pass # Not implemented yet
        elif record_type == 6: # kEnhancedReflashControllerTile
            if args['reboot'] == "True":
                skip_reboot_flag = 0
            else:
                skip_reboot_flag = 1
            return EnhancedReflashControllerRecord(bin_data, offset,
                                                   flags=skip_reboot_flag)
        else:
            raise BuildError("Invalid record type for this slot.",
                             slot=slot_number, record=record_type)
    else: # If slot is a tile
        if record_type == 1: # kReflashExternalTile
            return ReflashTileRecord(slot_number, bin_data, offset)
        else:
            raise BuildError("Invalid record type for this slot.",
                             slot=slot_number, record=record_type)


def _parse_slot_assignment(slot_assignment):
    """Parses the slot assignment with its slot number, record and arguments"""
    slot_number = _parse_slot_number(slot_assignment[0])
    record_type = _parse_slot_record(slot_assignment[2])
    args = _parse_slot_args(slot_assignment[3])

    return slot_number, record_type, args


def _parse_slot_number(slot_name):
    """Parses the slot string into the slot number"""
    if slot_name == 'controller':
        return 0
    elif not slot_name.startswith('slot '):
        raise BuildError("Invalid slot specifier that was not controller|slot X, where X is an integer", slot=slot_name)

    try:
        slot_number = int(slot_name[5:], 0)
    except ValueError:
        raise BuildError("Could not convert slot number to integer", slot=slot_name)

    return slot_number


def _parse_slot_record(slot_record):
    """Returns the appropriate record type based on the string"""
    if slot_record.lower() == 'reflash tile':
        return 1 # kReflashExternalTile
    elif slot_record.lower() == 'reflash controller':
        return 2 # kReflashControllerTile
    elif slot_record.lower() == 'execute rpc':
        return 3 # kExecuteRPCWithoutCheck
    elif slot_record.lower() == 'execute rpc check':
        return 4 # kExecuteRPCWithCheck
    elif slot_record.lower() == 'reset controller':
        return 5 # kResetController
    elif slot_record.lower() == 'enhanced reflash controller':
        return 6 # kEnhancedReflashControllerTile

    return 0

def _parse_slot_args(slot_args):
    """Returns a dict of arguments if it exists for this slot assignment

    The arguments need to follow a format of `argument_name=argument_value`.
    """
    args = {}

    if len(slot_args) == 0:
        return args

    for arg in slot_args:
        delimiter = arg.find("=")
        arg_name = arg[:delimiter]
        arg_value = arg[delimiter+1:]
        args[arg_name] = arg_value

    return args


def combine_trub_scripts(trub_scripts_list, out_file):
    """Combines trub scripts, processed from first to last"""

    resolver = ProductResolver.Create()

    files = [resolver.find_unique("trub_script", x).full_path for x in trub_scripts_list]

    env = Environment(tools=[])

    env.Command([os.path.join('build', 'output', out_file)], files,
                action=Action(_combine_trub_scripts_action, "Combining TRUB scripts at $TARGET"))


def _combine_trub_scripts_action(target, source, env):
    """Action to combine trub scripts"""

    records = []

    files = [str(x) for x in source]

    for script in files:
        if not os.path.isfile(script):
            raise BuildError("Path to script is not a valid file.",
                             script=script)
        
        trub_binary = _get_trub_binary(script)
        records += UpdateScript.FromBinary(trub_binary).records

    new_script = UpdateScript(records)

    with open(str(target[0]), "wb") as outfile:
        outfile.write(new_script.encode())


def get_sgf_checksum(file_name=None, sensorgraph=None):
    """Returns the device checksum from a sensorgraph file"""

    env = Environment(tools=[])

    env.Command([os.path.join('build', 'output', file_name)], [sensorgraph],
                action=Action(_get_sgf_checksum_action, "Building SGF Checksum file at $TARGET"))


def _get_sgf_checksum_action(target, source, env):
    """Action to get the SGF's checksum"""

    checksum = compile_sgf(str(source[0])).checksums

    with open(str(target[0]), "w") as outfile:
        outfile.write(str(checksum))


def _get_trub_binary(script_path):
    """Returns the encoded binary TRUB script"""

    with open(script_path, "rb") as script_file:
        trub_binary = script_file.read()

        return trub_binary