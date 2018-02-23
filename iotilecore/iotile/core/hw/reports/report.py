"""Base class for data streamed from an IOTile device
"""

import datetime
import dateutil.parser
from iotile.core.exceptions import NotFoundError


class IOTileReading(object):
    """Base class for readings streamed from IOTile device.

    Each reading represents a single time/value pair sent from an IOTile Device.
    Since many IOTile Devices do not have a hardware realtime clock, the timestamp
    that is assigned to a reading may only be a relative interval from a fixed
    event in the past, like the time the device turned on.

    If the user knows the absolute time for this event they can pass it as a datetime
    in time_base to turn the relative reading timestamp into an absolute datetime
    accessible as reading_time.

    Args:
        raw_time (int): the number of seconds since the device turned on
            when the reading was taken
        time_base (datetime): An optional estimate of when the device was
            last turned on so that we can calulate the actual time of the
            reading
        reading_time (datetime): An optional UTC time when this event was acquired.
            If combined with time_base, this value will take precedence and time_base
            and raw_time will be ignored.
        reading_id (int): An optional unique identifier for this reading that allows
            deduplication.  If no reading id is passed, InvalidReadingID is used.
        stream (int): The stream that this reading is part of
        value (int): The raw reading value
    """

    InvalidReadingID = 0

    def __init__(self, raw_time, stream, value, time_base=None, reading_id=None, reading_time=None):
        self.raw_time = raw_time
        self.stream = stream
        self.value = value

        if reading_id is None:
            reading_id = IOTileReading.InvalidReadingID

        self.reading_id = reading_id

        self.reading_time = reading_time
        if self.reading_time is None and time_base is not None and raw_time != IOTileEvent.InvalidRawTime:
            self.reading_time = time_base + datetime.timedelta(seconds=raw_time)

    def asdict(self):
        """Encode the data in this reading into a dictionary.

        Returns:
            dict: A dictionary containing the information from this reading.
        """

        timestamp_str = None
        if self.reading_time is not None:
            timestamp_str = self.reading_time.isoformat()

        return {
            'stream': self.stream,
            'device_timestamp': self.raw_time,
            'streamer_local_id': self.reading_id,
            'timestamp': timestamp_str,
            'value': self.value
        }

    @classmethod
    def FromDict(cls, obj):
        """Create an IOTileReading from the result of a previous call to asdict().

        Args:
            obj (dict): A dictionary produced by a call to IOTileReading.asdict()

        Returns:
            IOTileReading: The converted IOTileReading object.
        """

        timestamp = obj.get('timestamp')
        if timestamp is not None:
            timestamp = dateutil.parser.parse(timestamp)

        return IOTileReading(obj.get('device_timestamp'), obj.get('stream'), obj.get('value'), reading_id=obj.get('streamer_local_id'), reading_time=timestamp)

    def __eq__(self, other):
        return self.raw_time == other.raw_time and self.stream == other.stream and self.value == other.value and self.reading_id == other.reading_id

    def __str__(self):
        if self.reading_time is not None:
            return "Stream {}: {} at {}".format(self.stream, self.value, self.reading_time)
        else:
            return "Stream {}: {} at uncorrected time {}".format(self.stream, self.value, self.raw_time)


class IOTileEvent(object):
    """Base class for all unstructured events.

    An event is a dictionary with a small summary section and an arbitrarily
    large data section.  The difference between IOTileReading and IOTileEvent
    is that all readings are integers whereas events are key/value stores.

    There are two different key/value stores in an IOTileEvent because there
    may be a very large amount of raw data that is summarized into a smaller
    representationn.  It may be useful to know that separation so that we can
    store the large data somewhere different from where we store the summary.

    Args:
        raw_time (int): the number of seconds since the device turned on
            when the reading was taken.  This may be 0xFFFFFFFF if the raw
            time is not known.
        time_base (datetime): An optional estimate of when the device was
            last turned on so that we can calulate the actual time of the
            reading.  If this is passed it is combined with raw_time to figure
            out the UTC time when the reading was taken.
        reading_time (datetime): An optional UTC time when this event was acquired.
            If combined with time_base, this value will take precedence and time_base
            and raw_time will be ignored.
        reading_id (int): An optional unique identifier for this reading that allows
            deduplication.  If no reading id is passed, InvalidReadingID is used.
        stream (int): The stream that this reading is part of
        summary_data (dict): A dictionary of any summary data this event has.  You
            may pass None if there is no summary data.
        raw_data (dict): A dictionary (possibly very large) of all data associated
            with this event.  You may pass None if all data is contained in the
            summary_data member.
    """

    InvalidRawTime = 0xFFFFFFFF

    def __init__(self, raw_time, stream, summary_data, raw_data, time_base=None, reading_id=None, reading_time=None):
        self.raw_time = raw_time
        self.stream = stream

        if reading_id is None:
            reading_id = IOTileReading.InvalidReadingID

        self.reading_id = reading_id

        self.reading_time = reading_time
        if self.reading_time is None and time_base is not None and raw_time != IOTileEvent.InvalidRawTime:
            self.reading_time = time_base + datetime.timedelta(seconds=raw_time)

        self.summary_data = summary_data
        self.raw_data = raw_data

    def asdict(self):
        """Encode the data in this event into a dictionary.

        The dictionary returned from this method is a reference to the data
        stored in the IOTileEvent, not a copy.  It should be treated as read
        only.

        Returns:
            dict: A dictionary containing the information from this event.
        """

        return {
            'stream': self.stream,
            'device_timestamp': self.raw_time,
            'streamer_local_id': self.reading_id,
            'timestamp': self.reading_time,
            'extra_data': self.summary_data,
            'data': self.raw_data
        }

    @classmethod
    def FromDict(cls, obj):
        """Create an IOTileEvent from the result of a previous call to asdict().

        Args:
            obj (dict): A dictionary produced by a call to IOTileEvent.asdict()

        Returns:
            IOTileEvent: The converted IOTileEvent object.
        """

        timestamp = obj.get('timestamp')
        if timestamp is not None:
            timestamp = dateutil.parser.parse(timestamp)

        return IOTileEvent(obj.get('device_timestamp'), obj.get('stream'), obj.get('extra_data'), obj.get('data'), reading_id=obj.get('streamer_local_id'), reading_time=timestamp)

    def __str__(self):
        if self.reading_time is not None:
            return "Stream 0x{:04X}: Event at {}".format(self.stream, self.reading_time)
        elif self.raw_time != self.InvalidRawTime:
            return "Stream 0x{:04X}: Event at uncorrected time {}".format(self.stream, self.raw_time)

        return "Stream 0x{:04X}: Event at unknown time".format(self.stream)


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
        encrypted (bool): Whether this report is encrypted
        received_time (datetime): The time in UTC when this report was received from a device.
            If not received, the time is assumed to be utcnow().
    """

    def __init__(self, rawreport, signed, encrypted, received_time=None):
        self.visible_readings = []
        self.visible_events = []

        self.origin = None

        if received_time is None:
            self.received_time = datetime.datetime.utcnow()
        else:
            self.received_time = received_time

        self.raw_report = rawreport
        self.signed = signed
        self.encrypted = encrypted
        self.verified = False

        # We may not have any visible readings if our report is encrypted
        # and we do not have access to the decryption key.
        self.visible_readings, self.visible_events = self.decode()

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
        """Encode this report into a binary blob that could be decoded by a report format's decode method."""

        return self.raw_report

    def save(self, path):
        """Save a binary copy of this report

        Args:
            path (string): The path where we should save the binary copy of the report
        """

        data = self.encode()

        with open(path, "wb") as out:
            out.write(data)

    def serialize(self):
        """Turn this report into a dictionary that encodes all information including received timestamp
        """

        info = {}
        info['received_time'] = self.received_time
        info['encoded_report'] = str(self.encode())
        info['report_format'] = ord(info['encoded_report'][0])  # Report format is the first byte of the encoded report
        info['origin'] = self.origin

        return info

    def __str__(self):
        if self.verified:
            verified = "verified"
        else:
            verified = "not verified"

        if self.encrypted:
            enc = "encrypted"
        else:
            enc = "not encrypted"
        return "IOTile Report (length: %d, visible readings: %d, visible events: %d, %s and %s)" % (len(self.raw_report), len(self.visible_readings), len(self.visible_events), verified, enc)
