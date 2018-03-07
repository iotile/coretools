"""Update script record for reflashing a tile with new firmware."""

from __future__ import (print_function, absolute_import, unicode_literals)
import struct
from future.utils import python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError
from ..record import UpdateRecord, MatchQuality


@python_2_unicode_compatible
class ReflashTileRecord(UpdateRecord):
    """Reflash a tile at a specific slot with new firmware.

    This record embeds a new firmware image and targeting information for what
    slot is should be sent to.  When this record is executed on an IOTile device
    it will synchronously cause a tile to update its firmware and reset into the
    new firmware image before moving on to the next record.

    Args:
        slot (int): The slot number that we should target for reflashing
        raw_data (bytearray): The raw binary firmware data that we should
            program
        offset (int): The absolute memory offset at which raw_data starts.
        hardware_type (int): The hardware type of the tile that we are reflashing.
            This is currently unused and can be omitted.
    """

    RecordType = 1
    RecordHeaderLength = 20

    def __init__(self, slot, raw_data, offset, hardware_type=0):
        self.slot = slot
        self.raw_data = raw_data
        self.offset = offset
        self.hardware_type = hardware_type

    def encode_contents(self):
        """Encode the contents of this update record without including a record header.

        Returns:
            bytearary: The encoded contents.
        """

        header = struct.pack("<LL8sBxxx", self.offset, len(self.raw_data), _create_target(slot=self.slot), self.hardware_type)
        return bytearray(header) + self.raw_data

    @classmethod
    def MatchType(cls):
        """Return the record type that this record matches.

        All records must match an 8-bit record type field that is used to
        decode a binary script.  Note that multiple records may match the same
        8-bit record type if they have different levels of specificity.

        Returns:
            int: The single record type that this record matches.
        """

        return ReflashTileRecord.RecordType

    @classmethod
    def MatchQuality(cls, record_data, record_count=1):
        """Check how well this record matches the given binary data.

        This function will only be called if the record matches the type code
        given by calling MatchType() and this functon should check how well
        this record matches and return a quality score between 0 and 100, with
        higher quality matches having higher scores.  The default value should
        be MatchQuality.GenericMatch which is 50.  If this record does not
        match at all, it should return MatchQuality.NoMatch.

        Many times, only a single record type will match a given binary record
        but there are times when multiple different logical records produce
        the same type of record in a script, such as set_version and
        set_userkey both producing a call_rpc record with different RPC
        values.  The MatchQuality method is used to allow for rich decoding
        of such scripts back to the best possible record that created them.

        Args:
            record_data (bytearay): The raw record that we should check for
                a match.
            record_count (int): The number of binary records that are included
                in record_data.

        Returns:
            int: The match quality between 0 and 100.  You should use the
                constants defined in MatchQuality as much as possible.
        """

        if record_count > 1:
            return MatchQuality.NoMatch

        # Return a generic match so that someone can provide more details about
        # the firmware that loads onto a specific tile if they want.
        return MatchQuality.GenericMatch

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (NOT including the
        record type header) and it will decode it into a ReflashTileRecord.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass NOT including its 8 byte record header.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            ReflashTileRecord: The decoded reflash tile record.
        """

        if len(record_data) < ReflashTileRecord.RecordHeaderLength:
            raise ArgumentError("Record was too short to contain a full reflash record header", length=len(record_data), header_length=ReflashTileRecord.RecordHeaderLength)

        offset, data_length, raw_target, hardware_type = struct.unpack_from("<LL8sB3x", record_data)

        bindata = record_data[ReflashTileRecord.RecordHeaderLength:]
        if len(bindata) != data_length:
            raise ArgumentError("Embedded firmware length did not agree with actual length of embeded data", length=len(bindata), embedded_length=data_length)

        target = _parse_target(raw_target)
        if target['controller']:
            raise ArgumentError("Invalid targetting information, you cannot reflash a controller with a ReflashTileRecord", target=target)

        return ReflashTileRecord(target['slot'], bindata, offset, hardware_type)

    def __eq__(self, other):
        if not isinstance(other, ReflashTileRecord):
            return False

        return self.slot == other.slot and self.raw_data == other.raw_data and self.offset == other.offset and self.hardware_type == other.hardware_type

    def __str__(self):
        return "Reflash slot %d with %d (0x%X) bytes starting at offset %d (0x%X) (hardware_type: %d)" % (self.slot, len(self.raw_data), len(self.raw_data), self.offset, self.offset, self.hardware_type)


_MATCH_SLOT = 1
_MATCH_CONTROLLER = 2

def _create_target(slot):
    """Create binary targetting information.

    This function implements a subset of the targetting supported
    by an embedded tileman_matchdata_t structure but this is the
    only subset that is widely used.

    Args:
        slot (int): The slot that we wish to target

    Returns:
        bytes: an 8-byte blob containing targeting information.
    """

    return struct.pack("<B6xB", slot, 1)  # 1 is kTBMatchBySlot


def _parse_target(target):
    """Parse a binary targetting information structure.

    This function only supports extracting the slot number or controller from
    the target and will raise an ArgumentError if more complicated targetting
    is desired.

    Args:
        target (bytes): The binary targetting data blob.

    Returns:
        dict: The parsed targetting data
    """

    if len(target) != 8:
        raise ArgumentError("Invalid targetting data length", expected=8, length=len(target))
    slot, match_op = struct.unpack("<B6xB", target)

    if match_op == _MATCH_CONTROLLER:
        return {'controller': True, 'slot': 0}
    elif match_op == _MATCH_SLOT:
        return {'controller': False, 'slot': slot}

    raise ArgumentError("Unsupported complex targetting specified", match_op=match_op)
