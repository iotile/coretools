"""Update records that send an RPC."""

from __future__ import (print_function, absolute_import, unicode_literals)
from future.utils import python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError
from ..record import UpdateRecord, MatchQuality


@python_2_unicode_compatible
class ResetDeviceRecord(UpdateRecord):
    """Reset the device.

    This record will cause the device to reset and then continue processing
    the next record in the script after it restarts.  This synchronous reset
    behavior allows scripts that produce side effects only visible after a
    reset but required for processing the rest of the script to trigger and
    wait for a reset before continuing.
    """

    RecordType = 5

    def encode_contents(self):
        """Encode the contents of this update record without including a record header.

        Returns:
            bytearary: The encoded contents.
        """

        return bytearray()

    @classmethod
    def MatchType(cls):
        """Return the record type that this record matches.

        All records must match an 8-bit record type field that is used to
        decode a binary script.  Note that multiple records may match the same
        8-bit record type if they have different levels of specificity.

        Returns:
            int: The single record type that this record matches.
        """

        return cls.RecordType

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

        # Allow other records to override us by matching against specific kinds of RPCs
        return MatchQuality.PerfectMatch

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (NOT including the
        record type header) and it will decode it into a ResetDeviceRecord.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass NOT including its 8 byte record header.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            ResetDeviceRecord: The decoded reflash tile record.
        """

        if len(record_data) != 0:
            raise ArgumentError("Reset device record should have no included data", length=len(record_data))

        return ResetDeviceRecord()

    def __eq__(self, other):
        return isinstance(other, ResetDeviceRecord)

    def __str__(self):
        return "Reset device"
