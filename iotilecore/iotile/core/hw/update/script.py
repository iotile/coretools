"""A list of update records that specify a script for updating a device."""

from __future__ import (print_function, absolute_import, unicode_literals)
import struct
import hashlib
import logging
from hmac import compare_digest
from binascii import hexlify
from collections import namedtuple
from iotile.core.exceptions import ArgumentError, DataError
from .record import UpdateRecord, DeferMatching
from .records import UnknownRecord

ScriptHeader = namedtuple('ScriptHeader', ['header_length', 'authenticated', 'integrity_checked', 'encrypted'])


class UpdateScript(object):
    """An update script that consists of a list of UpdateRecord objects.

    Args:
        records (list of UpdateRecord): The records that make up this script.
    """

    SCRIPT_MAGIC = 0x1F2E3D4C
    SCRIPT_HEADER_LENGTH = 24

    logger = logging.getLogger(__name__)

    def __init__(self, records):
        self.records = records

    @classmethod
    def ParseHeader(cls, script_data):
        """Parse a script integrity header.

        This function makes sure any integrity hashes are correctly parsed and
        returns a ScriptHeader structure containing the information that it
        was able to parse out.

        Args:
            script_data (bytearray): The script that we should parse.

        Raises:
            ArgumentError: If the script contains malformed data that
                cannot be parsed.

        Returns:
            ScriptHeader: The parsed script header information
        """

        if len(script_data) < UpdateScript.SCRIPT_HEADER_LENGTH:
            raise ArgumentError("Script is too short to contain a script header", length=len(script_data), header_length=UpdateScript.SCRIPT_HEADER_LENGTH)

        embedded_hash, magic, total_length = struct.unpack_from("<16sLL", script_data)
        if magic != UpdateScript.SCRIPT_MAGIC:
            raise ArgumentError("Script has invalid magic value", expected=UpdateScript.SCRIPT_MAGIC, found=magic)

        if total_length != len(script_data):
            raise ArgumentError("Script length does not match embedded length", embedded_length=total_length, length=len(script_data))

        hashed_data = script_data[16:]

        sha = hashlib.sha256()
        sha.update(hashed_data)
        hash_value = sha.digest()[:16]

        if not compare_digest(embedded_hash, hash_value):
            raise ArgumentError("Script has invalid embedded hash", embedded_hash=hexlify(embedded_hash), calculated_hash=hexlify(hash_value))

        return ScriptHeader(UpdateScript.SCRIPT_HEADER_LENGTH, False, True, False)

    @classmethod
    def FromBinary(cls, script_data, allow_unknown=True):
        """Parse a binary update script.

        Args:
            script_data (bytearray): The binary data containing the script.
            allow_unknown (bool): Allow the script to contain unknown records
                so long as they have correct headers to allow us to skip them.
        Raises:
            ArgumentError: If the script contains malformed data that cannot
                be parsed.
            DataError: If the script contains unknown records and allow_unknown=False

        Returns:
            UpdateScript: The parsed update script.
        """

        curr = 0
        records = []

        header = cls.ParseHeader(script_data)
        curr = header.header_length

        cls.logger.debug("Parsed script header: %s, skipping %d bytes", header, curr)

        record_count = 0
        record_data = bytearray()
        partial_match = None
        match_offset = 0

        while curr < len(script_data):
            if len(script_data) - curr < UpdateRecord.HEADER_LENGTH:
                raise ArgumentError("Script ended with a partial record", remaining_length=len(script_data) - curr)

            # Add another record to our current list of records that we're parsing

            total_length, record_type = struct.unpack_from("<LB", script_data[curr:])
            cls.logger.debug("Found record of type %d, length %d", record_type, total_length)

            record_data += script_data[curr:curr+total_length]
            record_count += 1

            curr += total_length

            try:
                record = UpdateRecord.FromBinary(record_data, record_count)
            except DeferMatching as defer:
                # If we're told to defer matching, continue accumulating record_data
                # until we get a complete match.  If a partial match is available, keep track of
                # that partial match so that we can use it once the record no longer matches.

                if defer.partial_match is not None:
                    partial_match = defer.partial_match
                    match_offset = curr

                continue
            except DataError:
                if record_count > 1 and partial_match:
                    record = partial_match
                    curr = match_offset
                elif not allow_unknown:
                    raise
                elif allow_unknown and record_count > 1:
                    raise ArgumentError("A record matched an initial record subset but failed matching a subsequent addition without leaving a partial_match")
                else:
                    record = UnknownRecord(record_type, record_data[UpdateRecord.HEADER_LENGTH:])

            # Reset our record accumulator since we successfully matched one or more records
            record_count = 0
            record_data = bytearray()
            partial_match = None
            match_offset = 0

            records.append(record)

        return UpdateScript(records)

    def encode(self):
        """Encode this record into a binary blob.

        This binary blob could be parsed via a call to FromBinary().

        Returns:
            bytearray: The binary encoded script.
        """

        blob = bytearray()

        for record in self.records:
            blob += record.encode()

        header = struct.pack("<LL", self.SCRIPT_MAGIC, len(blob) + self.SCRIPT_HEADER_LENGTH)
        blob = header + blob

        sha = hashlib.sha256()
        sha.update(blob)
        hash_value = sha.digest()[:16]

        return bytearray(hash_value) + blob

    def __eq__(self, other):
        if not isinstance(other, UpdateScript):
            return False

        if len(self.records) != len(other.records):
            return False

        for record1, record2 in zip(self.records, other.records):
            if record1 != record2:
                return False

        return True

    def __ne__(self, other):
        return not self == other
