"""An enhanced reflash controller record."""

import struct
from iotile.core.exceptions import ArgumentError
from ..record import UpdateRecord, MatchQuality


class EnhancedReflashControllerRecord(UpdateRecord):
    """Enhanced Reflash for an IOTile controller.

        This record is based off the ReflashControllerRecord. This "enhanced"
        version contains additional parameters to allow for a more advanced
        way to reflash an IOTile device. The normal ReflashControllerRecord
        is simple and flashes binary data to flash offset. This record has
        options to allow for settings and flags to allow for future expansion.

        Args:
            raw_data (bytearray): The raw binary firmware data that we should
                program.
            base_address (int): The absolute memory offset at which raw_data 
                starts.
            image_type (int): *The type of firmware image
            flags (int): Specific flags to process
            compression_type (int): *How the appended image data is compressed
            compression_settings_length (int): *Length of compression settings
            compression_settings (bytearray): *Settings for compression
            preinstall_checks (bytearray): *Options to check during install 

        Note:
            The arguments marked with an asterisk(*) means that those features
            have not been implemented yet. This is just allowing for future
            expansion.
    """

    RecordType = 6
    RecordHeaderLength = 96

    def __init__(self, raw_data, base_address, image_type=0, flags=0,
                 compression_type=0, compression_settings_length=0,
                 compression_settings=bytearray(16),
                 preinstall_checks=bytearray(64)):
        self.raw_data = raw_data
        self.base_address = base_address
        self.image_type = image_type
        self.flags = flags
        self.compression_type = compression_type
        self.compression_settings_length = compression_settings_length
        self.compression_settings = compression_settings
        self.preinstall_checks = preinstall_checks

    def encode_contents(self):
        """Encode the contents of the enhanced reflash record.

        Returns:
            bytearray: The encoded contents
        """

        header = struct.pack("<LLLBBBB16s64s", self.base_address,
                             len(self.raw_data), len(self.raw_data),
                             self.image_type, self.flags, self.compression_type,
                             self.compression_settings_length,
                             self.compression_settings, self.preinstall_checks)

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

        return EnhancedReflashControllerRecord.RecordType

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

        if len(record_data) < EnhancedReflashControllerRecord.RecordHeaderLength:
            raise ArgumentError("Record was too short to contain a full enhanced reflash record header",
                                length=len(record_data), header_length=EnhancedReflashControllerRecord.RecordHeaderLength) 

        base_address, encoded_length, total_length, image_type, flags,\
        compression_type, compression_settings_length, compression_settings,\
        preinstall_checks  = struct.unpack_from("<LLLBBBB16s64s", record_data)

        bindata = record_data[EnhancedReflashControllerRecord.RecordHeaderLength:]
        if len(bindata) != total_length:
            raise ArgumentError("Embedded firmware length did not agree with actual length of embeded data",
                                length=len(bindata), embedded_length=total_length)

        return EnhancedReflashControllerRecord(bindata, base_address,
                                               image_type=image_type,
                                               flags=flags,
                                               compression_type=compression_type,
                                               compression_settings_length=compression_settings_length,
                                               compression_settings=compression_settings,
                                               preinstall_checks=preinstall_checks)

    def __eq__(self, other):
        if not isinstance(other, EnhancedReflashControllerRecord):
            return False

        return self.raw_data == other.raw_data and\
               self.base_address == other.base_address and\
               self.image_type == other.image_type and\
               self.flags == other.flags and\
               self.compression_type == other.compression_type and\
               self.compression_settings_length == other.compression_settings_length and\
               self.compression_settings == other.compression_settings and\
               self.preinstall_checks == other.preinstall_checks


    def __str__(self):
        return "Enhanced Reflash controller with %d (0x%X) bytes starting at base_address %d (0x%X)" %\
            (len(self.raw_data), len(self.raw_data), self.base_address, self.base_address)
