"""IOTileReport subclass for readings packaged as individual readings
"""

import datetime
from report import IOTileReport, IOTileReading
from iotile.core.utilities.packed import unpack

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

    def decode(self):
        """Decode this report into a single reading
        """

        fmt, _, stream, uuid, sent_timestamp, reading_timestamp, reading_value = unpack("<BBHLLLL", self.raw_report)
        assert fmt == 0

        #Estimate the UTC time when this device was turned on
        time_base = self.received_time - datetime.timedelta(seconds=sent_timestamp)

        reading = IOTileReading(reading_timestamp, stream, reading_value, time_base=time_base)
        self.origin = uuid
        return [reading]
