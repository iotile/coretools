"""Parsing routines for understanding binary streamer descriptors.

Binary streamer descriptors are the internal binary representation of
a streamer stored in an IOTile device's embedded firmware.
"""

import struct
from typedargs.exceptions import ArgumentError
from .slot import SlotIdentifier
from .stream import DataStreamSelector
from .streamer import DataStreamer
from .exceptions import SensorGraphSemanticError
from .parser.language import get_streamer_parser


def parse_binary_descriptor(bindata, sensor_log=None):
    """Convert a binary streamer descriptor into a string descriptor.

    Binary streamer descriptors are 20-byte binary structures that encode all
    information needed to create a streamer.  They are used to communicate
    that information to an embedded device in an efficent format.  This
    function exists to turn such a compressed streamer description back into
    an understandable string.

    Args:
        bindata (bytes): The binary streamer descriptor that we want to
            understand.
        sensor_log (SensorLog): Optional sensor_log to add this streamer to
            a an underlying data store.

    Returns:
        DataStreamer: A DataStreamer object representing the streamer.

        You can get a useful human readable string by calling str() on the
        return value.
    """

    if len(bindata) != 14:
        raise ArgumentError("Invalid length of binary data in streamer descriptor", length=len(bindata), expected=14, data=bindata)

    dest_tile, stream_id, trigger, format_code, type_code = struct.unpack("<8sHBBBx", bindata)

    dest_id = SlotIdentifier.FromEncoded(dest_tile)
    selector = DataStreamSelector.FromEncoded(stream_id)

    format_name = DataStreamer.KnownFormatCodes.get(format_code)
    type_name = DataStreamer.KnownTypeCodes.get(type_code)

    if format_name is None:
        raise ArgumentError("Unknown format code", code=format_code, known_code=DataStreamer.KnownFormatCodes)
    if type_name is None:
        raise ArgumentError("Unknown type code", code=type_code, known_codes=DataStreamer.KnownTypeCodes)

    with_other = None
    if trigger & (1 << 7):
        auto = False
        with_other = trigger & ((1 << 7) - 1)
    elif trigger == 0:
        auto = False
    elif trigger == 1:
        auto = True
    else:
        raise ArgumentError("Unknown trigger type for streamer", trigger_code=trigger)

    return DataStreamer(selector, dest_id, format_name, auto, type_name, with_other=with_other, sensor_log=sensor_log)


def create_binary_descriptor(streamer):
    """Create a packed binary descriptor of a DataStreamer object.

    Args:
        streamer (DataStreamer): The streamer to create a packed descriptor for

    Returns:
        bytes: A packed 14-byte streamer descriptor.
    """

    trigger = 0
    if streamer.automatic:
        trigger = 1
    elif streamer.with_other is not None:
        trigger = (1 << 7) | streamer.with_other

    return struct.pack("<8sHBBBx", streamer.dest.encode(), streamer.selector.encode(), trigger, streamer.KnownFormats[streamer.format], streamer.KnownTypes[streamer.report_type])


def parse_string_descriptor(string_desc):
    """Parse a string descriptor of a streamer into a DataStreamer object.

    Args:
        string_desc (str): The string descriptor that we wish to parse.

    Returns:
        DataStreamer: A DataStreamer object representing the streamer.
    """

    if not isinstance(string_desc, str):
        string_desc = str(string_desc)

    if not string_desc.endswith(';'):
        string_desc += ';'

    parsed = get_streamer_parser().parseString(string_desc)[0]

    realtime = 'realtime' in parsed
    broadcast = 'broadcast' in parsed
    encrypted = 'security' in parsed and parsed['security'] == 'encrypted'
    signed = 'security' in parsed and parsed['security'] == 'signed'
    auto = 'manual' not in parsed

    with_other = None
    if 'with_other' in parsed:
        with_other = parsed['with_other']
        auto = False

    dest = SlotIdentifier.FromString('controller')
    if 'explicit_tile' in parsed:
        dest = parsed['explicit_tile']

    selector = parsed['selector']

    # Make sure all of the combination are valid
    if realtime and (encrypted or signed):
        raise SensorGraphSemanticError("Realtime streamers cannot be either signed or encrypted")

    if broadcast and (encrypted or signed):
        raise SensorGraphSemanticError("Broadcast streamers cannot be either signed or encrypted")

    report_type = 'broadcast' if broadcast else 'telegram'
    dest = dest
    selector = selector

    if realtime or broadcast:
        report_format = u'individual'
    elif signed:
        report_format = u'signedlist_userkey'
    elif encrypted:
        raise SensorGraphSemanticError("Encrypted streamers are not yet supported")
    else:
        report_format = u'hashedlist'

    return DataStreamer(selector, dest, report_format, auto, report_type=report_type, with_other=with_other)
