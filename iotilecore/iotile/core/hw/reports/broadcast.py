"""The base class for all reports that are broadcast from a device without a connection.

The distinguishing feature between BroadcastReport objects and others like
IndividualReport are that BroadcastReports are not confined to a specific
connection so they needed to be treated specially.

All reports that could be Broadcast must inherit from BroadcastReport so that
all parts of CoreTools know not to drop the report if there is not an open
connection for the device in question.

Examples of ways you could receive a broadcast report are:
- bluetooth low energy broadcast readings
- MQTT posts in a topic
"""

import struct
from collections import namedtuple
import datetime
from iotile.core.exceptions import DataError
from .report import IOTileReading, IOTileReport

BroadcastHeader = namedtuple('BroadcastHeader', ['auth_type', 'reading_length', 'uuid', 'sent_timestamp', 'reserved'])


class BroadcastReport(IOTileReport):
    """Base class for all reports that are broadcast without a connection.

    This generic class supports a fixed encoding but does not yet support
    encryption/decryption or signing.  The encoding of this report is designed
    to accomodate a range of use cases and not be a binary match for any
    specific wire format that a BroadcastReport might be created from, such as
    part of a bluetooth advertisement packet.

    The encoding is designed to accomodate 1 or more IOTileReadings with a fixed
    size header and a variable length authentication block after the readings.
    """

    NO_AUTH = 0

    _HEADER_LENGTH = 16
    _AUTH_BLOCK_LENGTHS = {
        NO_AUTH: 0
    }

    ReportType = 3

    def __init__(self, rawreport, **kwargs):
        super(BroadcastReport, self).__init__(rawreport, signed=False, encrypted=False)

    @classmethod
    def _parse_header(cls, header):
        assert len(header) == cls._HEADER_LENGTH

        parsed = struct.unpack("<xBHLLL", header)
        return BroadcastHeader(*parsed)

    @classmethod
    def HeaderLength(cls):
        """Return the length of a header needed to calculate this report's length

        Returns:
            int: the length of the needed report header
        """

        return cls._HEADER_LENGTH

    @classmethod
    def ReportLength(cls, header):
        """Given a header of HeaderLength bytes, calculate the size of this report.

        Returns:
            int: The total length of the report including the header that we are passed.
        """

        parsed_header = cls._parse_header(header)

        auth_size = cls._AUTH_BLOCK_LENGTHS.get(parsed_header.auth_type)
        if auth_size is None:
            raise DataError("Unknown auth block size in BroadcastReport")

        return cls._HEADER_LENGTH + parsed_header.reading_length + auth_size

    @classmethod
    def FromReadings(cls, uuid, readings, sent_timestamp=0):
        """Generate a broadcast report from a list of readings and a uuid."""

        header = struct.pack("<BBHLLL", cls.ReportType, 0, len(readings)*16, uuid, sent_timestamp, 0)

        packed_readings = bytearray()

        for reading in readings:
            packed_reading = struct.pack("<HHLLL", reading.stream, 0, reading.reading_id, reading.raw_time, reading.value)
            packed_readings += bytearray(packed_reading)

        return BroadcastReport(bytearray(header) + packed_readings)

    def decode(self):
        """Decode this report into a list of visible readings."""

        parsed_header = self._parse_header(self.raw_report[:self._HEADER_LENGTH])

        auth_size = self._AUTH_BLOCK_LENGTHS.get(parsed_header.auth_type)
        assert auth_size is not None
        assert parsed_header.reading_length % 16 == 0

        time_base = self.received_time - datetime.timedelta(seconds=parsed_header.sent_timestamp)

        readings = self.raw_report[self._HEADER_LENGTH:self._HEADER_LENGTH + parsed_header.reading_length]
        parsed_readings = []

        for i in range(0, len(readings), 16):
            reading = readings[i:i+16]
            stream, _, reading_id, timestamp, value = struct.unpack("<HHLLL", reading)

            parsed = IOTileReading(timestamp, stream, value, time_base=time_base, reading_id=reading_id)
            parsed_readings.append(parsed)

        self.sent_timestamp = parsed_header.sent_timestamp
        self.origin = parsed_header.uuid

        return parsed_readings, []
