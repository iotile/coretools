"""Update script record for reflashing a tile with new firmware."""

from __future__ import (print_function, absolute_import, unicode_literals)
import struct
from future.utils import python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError
from ..record import UpdateRecord, MatchQuality


@python_2_unicode_compatible
class ReflashControllerRecord(UpdateRecord):
    """Reflash an IOTile controller with updated firmware.

    This record embedds the new firmware image in the record itself and
    always targets the controller tile at address 8.

    Args:
        raw_data (bytearray): The raw binary firmware data that we should
            program
        offset (int): The absolute memory offset at which raw_data starts.
    """

    RecordType = 2
    RecordHeaderLength = 8

    def __init__(self, raw_data, offset):
        self.raw_data = raw_data
        self.offset = offset

    def encode_contents(self):
        """Encode the contents of this update record without including a record header.

        Returns:
            bytearary: The encoded contents.
        """

        header = struct.pack("<LL", self.offset, len(self.raw_data))
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

        return ReflashControllerRecord.RecordType

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

        return MatchQuality.GenericMatch

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (NOT including the
        record type header) and it will decode it into a ReflashControllerRecord.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass NOT including its 8 byte record header.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            ReflashControllerRecord: The decoded reflash tile record.
        """

        if len(record_data) < ReflashControllerRecord.RecordHeaderLength:
            raise ArgumentError("Record was too short to contain a full reflash record header", length=len(record_data), header_length=ReflashControllerRecord.RecordHeaderLength)

        offset, data_length = struct.unpack_from("<LL", record_data)

        bindata = record_data[ReflashControllerRecord.RecordHeaderLength:]
        if len(bindata) != data_length:
            raise ArgumentError("Embedded firmware length did not agree with actual length of embeded data", length=len(bindata), embedded_length=data_length)

        return ReflashControllerRecord(bindata, offset)

    def __eq__(self, other):
        if not isinstance(other, ReflashControllerRecord):
            return False

        return self.raw_data == other.raw_data and self.offset == other.offset

    def __str__(self):
        return "Reflash controller with %d (0x%X) bytes starting at offset %d (0x%X)" % (len(self.raw_data), len(self.raw_data), self.offset, self.offset)
