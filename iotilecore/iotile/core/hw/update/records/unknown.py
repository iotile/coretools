"""A placeholder for unknown record types when we parse an UpdateScript."""

from __future__ import (print_function, absolute_import, unicode_literals)
import struct
from future.utils import python_2_unicode_compatible
from ..record import UpdateRecord


# pylint: disable=abstract-method, too-few-public-methods;The abstract methods should not be called, this is a placeholder class
@python_2_unicode_compatible
class UnknownRecord(UpdateRecord):
    """Reflash a tile at a specific slot with new firmware.

    This record embeds a new firmware image and targeting information for what
    slot is should be sent to.  When this record is executed on an IOTile
    device it will synchronously cause a tile to update its firmware and reset
    into the new firmware image before moving on to the next record.

    Args:
        record_type (int): The unknwn record type that we are supposed to
            process.
        raw_data (bytearray): The raw record contents.
    """

    def __init__(self, record_type, raw_data):
        self.record_type = record_type
        self.record_contents = raw_data

    def encode(self):
        """Encode this record into binary, suitable for embedded into an update script.

        This function just adds the required record header and copies the raw data
        we were passed in verbatim since we don't know what it means

        Returns:
            bytearary: The binary version of the record that could be parsed via
                a call to UpdateRecord.FromBinary()
        """

        header = struct.pack("<LB3x", len(self.record_contents) + UpdateRecord.HEADER_LENGTH, self.record_type)
        return bytearray(header) + self.record_contents

    def __eq__(self, other):
        if not isinstance(other, UnknownRecord):
            return False

        return self.record_type == other.record_type

    def __str__(self):
        return "Unknown record type %d, length: %d" % (self.record_type, len(self.record_contents))
