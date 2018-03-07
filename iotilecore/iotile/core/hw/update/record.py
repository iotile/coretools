"""All update scripts are composed of a series of records.

All records must inherit from this base class and implement its required methods.
"""

from __future__ import (print_function, absolute_import, unicode_literals)
import struct
from iotile.core.exceptions import ArgumentError, DataError


# pylint: disable=too-few-public-methods;This is an enum class
class MatchQuality(object):
    """Mnemonics for indicating different levels of record matching."""

    NoMatch = 0
    GenericMatch = 50
    PerfectMatch = 100
    DeferMatch = 1000
    PartialMatch = 1100


class DeferMatching(Exception):
    """An exception to indicate that we should accumulate records and match later."""
    def __init__(self, matching_class, partial=None):
        super(DeferMatching, self).__init__()

        self.matching_class = matching_class
        self.partial_match = partial


class UpdateRecord(object):
    """The base class for all update actions inside of an update script."""

    HEADER_LENGTH = 8

    # A map of record types to potentially matching record classes
    KNOWN_CLASSES = {}
    PLUGINS_LOADED = False

    @classmethod
    def MatchType(cls):
        """Return the record type that this record matches.

        All records must match an 8-bit record type field that is used to
        decode a binary script.  Note that multiple records may match the same
        8-bit record type if they have different levels of specificity.

        Returns:
            int: The single record type that this record matches.
        """

        raise NotImplementedError()

    def encode(self):
        """Encode this record into binary, suitable for embedded into an update script.

        This function just adds the required record header and delegates all
        work to the subclass implemention of encode_contents().

        Returns:
            bytearary: The binary version of the record that could be parsed via
                a call to UpdateRecord.FromBinary()
        """

        contents = self.encode_contents()
        record_type = self.MatchType()

        header = struct.pack("<LB3x", len(contents) + UpdateRecord.HEADER_LENGTH, record_type)

        return bytearray(header) + contents

    def encode_contents(self):
        """Encode the contents of this update record without including a record header.

        Returns:
            bytearary: The encoded contents.
        """

        raise NotImplementedError()

    @classmethod
    def LoadPlugins(cls):
        """Load all registered iotile.update_record plugins."""

        if cls.PLUGINS_LOADED:
            return

        import pkg_resources

        for entry in pkg_resources.iter_entry_points('iotile.update_record'):
            record = entry.load()
            cls.RegisterRecordType(record)

        cls.PLUGINS_LOADED = True

    @classmethod
    def MatchQuality(cls, record_data, record_count=1):
        """Check how well this record matches the given binary data.

        This function will only be called if the record matches the type code
        given by calling MatchType() and this function should check how well
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
            record_count (int): If we are asked for a match on multiple
                records in a row, because we previously returned MatchQuality.DeferMatch
                then this will indicate how many binary records are included together.

        Returns:
            int: The match quality between 0 and 100.  You should use the
                constants defined in MatchQuality as much as possible.  The only
                exception to the 0 to 100 rules is if you retern MatchQuality.DeferMatch
                which means that we are matching a multi-record statement with a single
                logical UpdateRecord.
        """

        raise NotImplementedError()

    @classmethod
    def RegisterRecordType(cls, record_class):
        """Register a known record type in KNOWN_CLASSES.

        Args:
            record_class (UpdateRecord): An update record subclass.
        """

        record_type = record_class.MatchType()
        if record_type not in UpdateRecord.KNOWN_CLASSES:
            UpdateRecord.KNOWN_CLASSES[record_type] = []

        UpdateRecord.KNOWN_CLASSES[record_type].append(record_class)

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (including the record
        type header) and it will return the best record class match that it
        can find for that record.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass including its 4 byte record header.
            record_count (int): If we are asked to create a record from multiple
                records, the record_data will be passed to the record subclass
                with headers intact since there will be more than one header.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.
            DataError: If there is no matching record type registered.

        Returns:
            UpdateRecord: A subclass of UpdateRecord based on what record
                type matches the best.
        """

        # Make sure any external record types are registered
        cls.LoadPlugins()

        if len(record_data) < UpdateRecord.HEADER_LENGTH:
            raise ArgumentError("Record data is too short to contain a record header", length=len(record_data), header_length=UpdateRecord.HEADER_LENGTH)

        total_length, record_type = struct.unpack_from("<LB3x", record_data)

        if record_count == 1 and len(record_data) != total_length:
            raise ArgumentError("Record data is corrupt, embedded length does not agree with actual length", length=len(record_data), embedded_length=total_length)

        record_classes = UpdateRecord.KNOWN_CLASSES.get(record_type, [])
        if len(record_classes) == 0:
            raise DataError("No matching record type found for record", record_type=record_type, known_types=[x for x in UpdateRecord.KNOWN_CLASSES])

        best_match = MatchQuality.NoMatch
        matching_class = None

        for record_class in record_classes:
            match_data = record_data[UpdateRecord.HEADER_LENGTH:]

            if record_count > 1:
                match_data = record_data

            quality = record_class.MatchQuality(match_data, record_count)

            if quality > best_match:
                best_match = quality
                matching_class = record_class

        if best_match == MatchQuality.DeferMatch:
            raise DeferMatching(matching_class)
        elif best_match == MatchQuality.PartialMatch:
            raise DeferMatching(matching_class, matching_class.FromBinary(match_data, record_count))

        if matching_class is None:
            raise DataError("Record type found but no specific class reported a match", record_type=record_type, considered_classes=record_classes)

        return matching_class.FromBinary(match_data, record_count)

    def __ne__(self, other):
        return not self == other
