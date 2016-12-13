"""IOTileReport subclass for readings packaged as individual readings
"""

import datetime
import struct
from report import IOTileReport, IOTileReading
from iotile.core.utilities.packed import unpack
from iotile.core.exceptions import ArgumentError


class IndividualReadingReport(IOTileReport):
    """Report format where every reading is packaged in a 20 byte frame

    Args:
        rawreport (bytearray): The raw data of this report
    """

    ReportType = 0

    def __init__(self, rawreport, **kwargs):
        super(IndividualReadingReport, self).__init__(rawreport, signed=False, encrypted=False, **kwargs)

    @classmethod
    def HeaderLength(cls):
        """Return the length of a header needed to calculate this report's length

        Returns:
            int: the length of the needed report header
        """

        return 1

    @classmethod
    def ReportLength(cls, header):
        """Given a header of HeaderLength bytes, calculate the size of this report
        """

        return 20

    @classmethod
    def FromReadings(cls, uuid, readings):
        """Generate an instance of the report format from a list of readings and a uuid
        """

        if len(readings) != 1:
            raise ArgumentError("IndividualReading reports must be created with exactly one reading", num_readings=len(readings))

        reading = readings[0]
        data = struct.pack("<BBHLLLL", 0, 0, reading.stream, uuid, 0, reading.raw_time, reading.value)
        return IndividualReadingReport(data)

    def decode(self):
        """Decode this report into a single reading
        """

        fmt, _, stream, uuid, sent_timestamp, reading_timestamp, reading_value = unpack("<BBHLLLL", self.raw_report)
        assert fmt == 0

        #Estimate the UTC time when this device was turned on
        time_base = self.received_time - datetime.timedelta(seconds=sent_timestamp)

        reading = IOTileReading(reading_timestamp, stream, reading_value, time_base=time_base)
        self.origin = uuid
        self.sent_timestamp = sent_timestamp

        return [reading]

    def encode(self):
        """Turn this report into a serialized bytearray that could be decoded with a call to decode
        """

        reading = self.visible_readings[0]
        data = struct.pack("<BBHLLLL", 0, 0, reading.stream, self.origin, self.sent_timestamp, reading.raw_time, reading.value)

        return bytearray(data)