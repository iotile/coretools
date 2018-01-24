"""Parsing routines for understanding binary streamer descriptors.

Binary streamer descriptors are the internal binary representation of
a streamer stored in an IOTile device's embedded firmware.
"""

from __future__ import (unicode_literals, absolute_import, print_function)
from builtins import str
import struct
from typedargs.exceptions import ArgumentError
from .slot import SlotIdentifier
from .stream import DataStreamSelector
from .streamer import DataStreamer


def parse_binary_descriptor(bindata):
    """Convert a binary streamer descriptor into a string descriptor.

    Binary streamer descriptors are 20-byte binary structures that encode all
    information needed to create a streamer.  They are used to communicate
    that information to an embedded device in an efficent format.  This
    function exists to turn such a compressed streamer description back into
    an understandable string.

    Args:
        bindata (bytes): The binary streamer descriptor that we want to
            understand.

    Returns:
        str: A string description of the streamer.
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

    manual = "manual " if not auto else ""
    realtime = "realtime " if format_name == 'individual' else ""

    security = ""
    if format_name == 'signedlist_userkey':
        security = "signed "

    to_slot = ""
    if not dest_id.controller:
        to_slot = " to " + str(dest_id)

    with_statement = ""
    if with_other is not None:
        with_statement = " with streamer %d" % with_other

    template = "{manual}{security}{realtime}streamer on {selector}{to_slot}{with_other}"
    return template.format(manual=manual, security=security, realtime=realtime, selector=selector,
                           with_other=with_statement, to_slot=to_slot)
