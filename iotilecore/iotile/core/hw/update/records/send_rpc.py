"""Update records that send an RPC."""

from __future__ import (print_function, absolute_import, unicode_literals)
import struct
from binascii import hexlify
from collections import namedtuple
from future.utils import python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError
from ..record import UpdateRecord, MatchQuality

RPCInfo = namedtuple("RPCInfo", ["command", "address", "response_size", "payload"])


@python_2_unicode_compatible
class SendRPCRecord(UpdateRecord):
    """Send an RPC without checking the response.

    The record causes the remote bridge script processor to send an RPC
    and not to check the contents of the result.  It still checks that the
    response size corresponds with what is expected but does not check the
    contents explicitly.

    Args:
        address (int): The address that we want to send an RPC to.
        rpc_id (int): The RPC id that we want to call
        payload (bytearray): The RPC payload that we want to send
        response_size (int): The fixed size of the expected response.  If this is None
            then the response is of a variable size and not checked explicitly.
    """

    RecordType = 3
    RecordHeaderLength = 4

    def __init__(self, address, rpc_id, payload=None, response_size=None):
        if payload is None:
            payload = bytearray()

        self.address = address
        self.rpc_id = rpc_id
        self.payload = payload
        self.variable_size = response_size is None
        self.fixed_response_size = response_size

        if self.fixed_response_size is not None and self.fixed_response_size >= (1 << 7):
            raise ArgumentError("RPC specifies a fixed response size greater than 1 << 7, which is the largest supported", size=response_size)

    def encode_contents(self):
        """Encode the contents of this update record without including a record header.

        Returns:
            bytearary: The encoded contents.
        """

        if self.variable_size:
            resp_length = 1
        else:
            resp_length = self.fixed_response_size << 1

        header = struct.pack("<HBB", self.rpc_id, self.address, resp_length)
        return bytearray(header) + self.payload

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
        return MatchQuality.GenericMatch

    @classmethod
    def _parse_rpc_info(cls, record_data):
        if len(record_data) < SendRPCRecord.RecordHeaderLength:
            raise ArgumentError("SendRPC record is too short", header_length=4, length=len(record_data))

        cmd, address, resp_length = struct.unpack_from("<HBB", record_data)
        payload = record_data[cls.RecordHeaderLength:]

        return RPCInfo(cmd, address, resp_length, payload)

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (NOT including the
        record type header) and it will decode it into a SendRPCRecord.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass NOT including its 8 byte record header.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            SendRPCRecord: The decoded reflash tile record.
        """

        cmd, address, resp_length, payload = cls._parse_rpc_info(record_data)

        # The first bit is 1 if we do not have a fixed length
        # The next 7 bits encode the fixed length if we do have a fixed length
        fixed_length = resp_length >> 1
        if resp_length & 0b1:
            fixed_length = None

        return cls(address, cmd, payload, fixed_length)

    def __str__(self):
        return "Call RPC 0x%X on tile at %d with payload '%s'" % (self.rpc_id, self.address, hexlify(self.payload))

    def __eq__(self, other):
        if not isinstance(other, SendRPCRecord):
            return False

        return self.rpc_id == other.rpc_id and self.address == other.address and self.payload == other.payload and self.fixed_response_size == other.fixed_response_size


@python_2_unicode_compatible
class SendErrorCheckingRPCRecord(SendRPCRecord):
    """Send an RPC and check for errors in the response.

    The record causes the remote bridge script processor to send an RPC and to
    check that the response (which must be a 32-bit error code) is 0
    indicating no error.

    Args:
        address (int): The address that we want to send an RPC to.
        rpc_id (int): The RPC id that we want to call
        payload (bytearray): The RPC payload that we want to send
        response_size (int): The fixed size of the expected response.  This must be 4
            bytes since it must return a single 32-bit error code.
    """

    RecordType = 4

    def __init__(self, address, rpc_id, payload=None, response_size=None):
        if response_size != 4:
            raise ArgumentError("Error handling RPCs must have a fixed response size of 4 bytes", response_size=response_size)

        super(SendErrorCheckingRPCRecord, self).__init__(address, rpc_id, payload, response_size)

    def __str__(self):
        return "Call RPC 0x%X on tile at %d with payload '%s' and check for errors" % (self.rpc_id, self.address, hexlify(self.payload))

    def __eq__(self, other):
        if not isinstance(other, SendErrorCheckingRPCRecord):
            return False

        return self.rpc_id == other.rpc_id and self.address == other.address and self.payload == other.payload and self.fixed_response_size == other.fixed_response_size

    @classmethod
    def parse_multiple_rpcs(cls, record_data):
        """Parse record_data into multiple error checking rpcs."""

        rpcs = []

        while len(record_data) > 0:
            total_length, record_type = struct.unpack_from("<LB3x", record_data)
            if record_type != SendErrorCheckingRPCRecord.RecordType:
                raise ArgumentError("Record set contains a record that is not an error checking RPC", record_type=record_type)

            record_contents = record_data[8: total_length]
            parsed_rpc = cls._parse_rpc_info(record_contents)
            rpcs.append(parsed_rpc)

            record_data = record_data[total_length:]

        return rpcs
