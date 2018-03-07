"""An UpdateScript record that sets a config variable."""

from __future__ import unicode_literals, absolute_import, print_function
import struct
from binascii import hexlify
from future.utils import python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.update.record import MatchQuality, UpdateRecord
from iotile.core.hw.update.records import SendErrorCheckingRPCRecord
from iotile.sg import SlotIdentifier


#pylint: disable=abstract-method;Method encode_contents is not overriden because we directly override encode
@python_2_unicode_compatible
class SetConfigRecord(UpdateRecord):
    """Set a config value on a specific tile.

    Args:
        tile (SlotIdentifier): The target tile
        config_id (int): The id of the config variable we want to set
        data (bytearray): The raw data that we wish to load into the
            config variable.
    """

    RecordType = 4

    BEGIN_CONFIG_RPC = 0x2A07
    PUSH_CONFIG_RPC = 0x2A08
    END_CONFIG_RPC = 0x2A09

    def __init__(self, tile, config_id, data):
        self.target = tile
        self.config_id = config_id
        self.data = data

    def encode(self):
        """Encode this record into binary, suitable for embedded into an update script.

        This function will create multiple records that correspond to the actual
        underlying rpcs that SetConfigRecord turns into.

        Returns:
            bytearary: The binary version of the record that could be parsed via
                a call to UpdateRecord.FromBinary()
        """

        begin_payload = struct.pack("<H8s", self.config_id, self.target.encode())
        start_record = SendErrorCheckingRPCRecord(8, self.BEGIN_CONFIG_RPC, begin_payload, 4)
        end_record = SendErrorCheckingRPCRecord(8, self.END_CONFIG_RPC, bytearray(), 4)
        push_records = []

        for i in range(0, len(self.data), 20):
            chunk = self.data[i:i+20]
            push_record = SendErrorCheckingRPCRecord(8, self.PUSH_CONFIG_RPC, chunk, 4)
            push_records.append(push_record)

        out_blob = bytearray()
        out_blob += start_record.encode()

        for push_record in push_records:
            out_blob += push_record.encode()

        out_blob += end_record.encode()
        return out_blob

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

        if record_count == 1:
            cmd, address, _resp_length, _payload = SendErrorCheckingRPCRecord._parse_rpc_info(record_data)

            if cmd == cls.BEGIN_CONFIG_RPC and address == 8:
                return MatchQuality.DeferMatch

            return MatchQuality.NoMatch

        # To see if this is a set_config variable record set, we need to decode all of
        # the records and make sure each is an error checking rpc with the right rpc id
        try:
            rpcs = SendErrorCheckingRPCRecord.parse_multiple_rpcs(record_data)

            push_commands = rpcs[1:-1]

            for cmd in push_commands:
                cmd_id, addr = cmd[:2]
                if cmd_id != cls.PUSH_CONFIG_RPC or addr != 8:
                    return MatchQuality.NoMatch

            last_cmd, last_addr = rpcs[-1][:2]
            if last_cmd == cls.END_CONFIG_RPC and last_addr == 8:
                return MatchQuality.PerfectMatch
        except ArgumentError:
            return MatchQuality.NoMatch

        return MatchQuality.DeferMatch

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This is a multi-action record that matches a pattern of error checking
        RPC calls:
        begin config
        push config data
        <possibly multiple>
        end config

        Args:
            record_data (bytearray): The raw record data that we wish to parse.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            SetConfigRecord: The decoded tile records.
        """

        rpcs = SendErrorCheckingRPCRecord.parse_multiple_rpcs(record_data)

        start_rpc = rpcs[0]
        push_rpcs = rpcs[1:-1]

        try:
            config_id, raw_target = struct.unpack("<H8s", start_rpc.payload)
            target = SlotIdentifier.FromEncoded(raw_target)
        except ValueError:
            raise ArgumentError("Could not parse payload on begin config rpc", payload=start_rpc.payload)

        payload = bytearray()
        for rpc in push_rpcs:
            payload += rpc.payload

        return SetConfigRecord(target, config_id, payload)

    def __str__(self):
        return "Set config variable 0x%X on %s to 'hex:%s'" % (self.config_id, self.target, hexlify(self.data))
