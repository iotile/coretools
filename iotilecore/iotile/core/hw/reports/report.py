"""Base class for data streamed from an IOTile device
"""

class IOTileReading(object):
    """Base class for readings streamed from IOTile device

    Args:
        timestamp (int): the number of seconds since the device turned on
            when the reading was taken
        value (bytearray): the raw reading value
    """

    def __init__(self, timestamp, value):
        self.timestamp = timestamp
        self.value = bytearray(value)

    def __str__(self):
        return "{}: {}".format(self.timestamp, repr(self.value))


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
    - class method ParseReport(cls, report_data)
        function that takes ReportLength() bytes and produces an instance of a subclass of 
        IOTileReport containing the parsed readings.  

    
    
    Args:
        readings (list): A list of readings inside this IOTileReport
    """

    def __init__(self, readings=[]):
        self.readings = readings

    @classmethod
    def HeaderLength()

    def __str__(self):
        return "IOTile Report with %d readings" % len(self.readings)
