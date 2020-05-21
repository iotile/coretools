"""Creates a binary UpdateScript object containing the sensor graph and any config information."""

import struct
from iotile.sg.update import (AddNodeRecord, AddStreamerRecord, SetConfigRecord, SetConstantRecord,
                              SetGraphOnlineRecord, PersistGraphRecord, ClearDataRecord, ResetGraphRecord,
                              ClearConfigVariablesRecord)
from iotile.core.hw.update.records import SetDeviceTagRecord
from iotile.core.hw.update import UpdateScript
from iotile.core.exceptions import ArgumentError


def format_script(sensor_graph):
    """Create a binary script containing this sensor graph.

    This function produces a repeatable script by applying a known sorting
    order to all constants and config variables when iterating over those
    dictionaries.

    Args:
        sensor_graph (SensorGraph): the sensor graph that we want to format

    Returns:
        bytearray: The binary script data.

    """

    records = []

    records.append(SetGraphOnlineRecord(False, address=8))
    records.append(ClearDataRecord(address=8))
    records.append(ResetGraphRecord(address=8))

    for node in sensor_graph.nodes:
        records.append(AddNodeRecord(str(node), address=8))

    for streamer in sensor_graph.streamers:
        records.append(AddStreamerRecord(streamer, address=8))

    for stream, value in sorted(sensor_graph.constant_database.items(), key=lambda x: x[0].encode()):
        records.append(SetConstantRecord(stream, value, address=8))

    records.append(PersistGraphRecord(address=8))

    records.append(ClearConfigVariablesRecord())
    for slot in sorted(sensor_graph.config_database, key=lambda x: x.encode()):
        for config_id in sorted(sensor_graph.config_database[slot]):
            config_type, value = sensor_graph.config_database[slot][config_id]
            byte_value = _convert_to_bytes(config_type, value)

            records.append(SetConfigRecord(slot, config_id, byte_value))

    # If we have an app tag and version set program them in
    app_tag = sensor_graph.metadata_database.get('app_tag')
    app_version = sensor_graph.metadata_database.get('app_version')

    if app_tag is not None:
        records.append(SetDeviceTagRecord(app_tag=app_tag, app_version=app_version))

    script = UpdateScript(records)
    return script.encode()


def _convert_to_bytes(type_name, value):
    """Convert a typed value to a binary array"""

    int_types = {'uint8_t': 'B', 'int8_t': 'b', 'uint16_t': 'H', 'int16_t': 'h', 'uint32_t': 'L', 'int32_t': 'l'}

    type_name = type_name.lower()

    is_array = False
    if type_name[-2:] == '[]':
        if value[0] != '[' or value[-1] != ']':
            raise ArgumentError("Array value improperly formated, must be a stringified list")
        is_array = True
        type_name = type_name[:-2]

    if type_name not in int_types and type_name not in ['string', 'binary']:
        raise ArgumentError('Type must be a known integer type, integer type array, string', known_integers=int_types.keys(), actual_type=type_name)

    if type_name == 'string':
        #value should be passed as a string
        bytevalue = bytearray(value, 'utf-8')
    elif type_name == 'binary':
        bytevalue = bytearray(value)
    elif is_array:
        value = [int(n,0) for n in value[1:-1].split(',')]
        bytevalue = bytearray(struct.pack("<%s" % (int_types[type_name]*len(value)), *value))
    else:
        bytevalue = struct.pack("<%s" % int_types[type_name], value)

    return bytevalue
