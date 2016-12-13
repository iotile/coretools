"""Base class for data streamed from an IOTile device
"""

import datetime
from iotile.core.exceptions import NotFoundError

class IOTileReading(object):
    """Base class for readings streamed from IOTile device

    Args:
        raw_time (int): the number of seconds since the device turned on
            when the reading was taken
        time_base (datetime): An optional estimate of when the device was
            last turned on so that we can calulate the actual time of the
            reading
        stream (int): The stream that this reading is part of
        value (bytearray): the raw reading value
    """

    def __init__(self, raw_time, stream, value, time_base=None):
        self.raw_time = raw_time
        self.stream = stream
        self.value = value

        self.reading_time = None
        if time_base is not None:
            self.reading_time = time_base + datetime.timedelta(seconds=raw_time)

    def __str__(self):
        if self.reading_time is not None:
            return "Stream {}: {} at {}".format(self.stream, self.value, self.reading_time)
        else:
            return "Stream {}: {} at uncorrected time {}".format(self.stream, self.value, self.raw_time)

class IOTileReport(object):
    """Base class for data streamed from an IOTile device.

    All IOTileReports must derive from this class and must implement the following interface

    - class method HeaderLength(cls)
        function returns the number of bytes that must be read before the total length of
        the report can be determined.  HeaderLength() must always be less than or equal to
        the length of the smallest version of this report.
    - class method ReportLength(cls, header):
        function that takes HeaderLength() bytes and returns the total size of the report,
        including the header.
    - class method FromReadings(cls, uuid, readings)
        function that creates an instance of an IOTileReport subclass from a list of readings
        and a device uuid.
    - propery ReportType:
        The one byte type code that defines this report type
    - instance method verify(self):
        function that verifies that a report is correctly received and, if possible, that
        the sender is who it says it is.
    - instance method decode(self):
        function that decodes a report into a series of IOTileReading objects. The function
        should return a list of readings.
    - instance method serialize(self):
        function that should turn the report into a serialized bytearray that could be
        decoded with decode().

    Args:
        rawreport (bytearray): The raw data of this report
        signed (bool): Whether this report is signed to specify who it is from
        encrypted (bool): Whether this report is encrypted\
        received_time (datetime): The time in UTC when this report was received from a device.
            If not received, the time is assumed to be utcnow().
    """

    def __init__(self, rawreport, signed, encrypted, received_time=None):
        self.visible_readings = []
        self.origin = None

        if received_time is None:
            self.received_time = datetime.datetime.utcnow()
        else:
            self.received_time = received_time

        self.raw_report = rawreport
        self.signed = signed
        self.encrypted = encrypted
        self.decoded = False
        self.verified = False

        #If we're able to, decode the report immediately 
        if not encrypted:
            self.visible_readings = self.decode()
            self.decoded = True

    @classmethod
    def HeaderLength(cls):
        """Return the length of a header needed to calculate this report's length

        Returns:
            int: the length of the needed report header
        """

        raise NotFoundError("IOTileReport HeaderLength needs to be overridden")

    @classmethod
    def ReportLength(cls, header):
        """Given a header of HeaderLength bytes, calculate the size of this report
        """

        raise NotFoundError("IOTileReport ReportLength needs to be overriden")

    def decode(self):
        """Decode a raw report into a series of readings
        """

        raise NotFoundError("IOTileReport decode needs to be overriden")

    def encode(self):
        """Encode this report into a binary blob that could be decoded by a report format's decode method
        """

        return self.raw_report

    def serialize(self):
        """Turn this report into a dictionary that encodes all information including received timestamp
        """

        info = {}
        info['received_time'] = self.received_time
        info['encoded_report'] = str(self.encode())
        info['report_format'] = ord(info['encoded_report'][0]) #Report format is the first byte of the encoded report
        info['origin'] = self.origin

        return info

    def __str__(self):
        return "IOTile Report of length %d with %d visible readings" % (len(self.raw_report), len(self.visible_readings))
