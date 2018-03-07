from __future__ import unicode_literals, absolute_import, print_function
from future.utils import python_2_unicode_compatible
from iotile.core.hw.update.record import MatchQuality
from iotile.core.hw.update.records import SendErrorCheckingRPCRecord
from iotile.sg.node_descriptor import parse_binary_descriptor, create_binary_descriptor


@python_2_unicode_compatible
class AddNodeRecord(SendErrorCheckingRPCRecord):
    """Add a sensorgraph node to a device.

    Args:
        descriptor (str): A string node descriptor for the node that
            we wish to add to our embedded sensorgraph.
        address (int): The address of the tile running a sensorgraph
            engine that we wish to add our node to.
    """

    RPC_ID = 0x2003

    def __init__(self, descriptor, address):
        payload = create_binary_descriptor(descriptor)
        super(AddNodeRecord, self).__init__(address, AddNodeRecord.RPC_ID, payload, response_size=4)

        self.descriptor = descriptor

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

        cmd, _address, _resp_length, _payload = cls._parse_rpc_info(record_data)

        if cmd == AddNodeRecord.RPC_ID:
            return MatchQuality.PerfectMatch

        return MatchQuality.NoMatch

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (NOT including the
        record type header) and it will decode it into a AddNodeRecord.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass NOT including its 8 byte record header.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            AddNodeRecord: The decoded reflash tile record.
        """

        _cmd, address, _resp_length, payload = cls._parse_rpc_info(record_data)

        descriptor = parse_binary_descriptor(payload)
        return AddNodeRecord(descriptor, address=address)

    def __str__(self):
        return "Add sensorgraph node '%s'" % self.descriptor
