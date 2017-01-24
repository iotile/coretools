"""IOTileReport subclass for readings packaged as individual readings
"""

import datetime
import struct
from report import IOTileReport, IOTileReading
from iotile.core.utilities.packed import unpack
from iotile.core.exceptions import ArgumentError, NotFoundError, EnvironmentError
import iotile.core.hw.auth.auth_provider as auth_provider
from iotile.core.hw.auth.auth_chain import ChainedAuthProvider

class SignedListReport(IOTileReport):
    """A report that consists of a signed list of readings.

    Args:
        rawreport (bytearray): The raw data of this report
    """

    ReportType = 1

    def __init__(self, rawreport, **kwargs):
        super(SignedListReport, self).__init__(rawreport, signed=True, encrypted=False, **kwargs)

    @classmethod
    def HeaderLength(cls):
        """Return the length of a header needed to calculate this report's length

        Returns:
            int: the length of the needed report header
        """

        return 20

    @classmethod
    def ReportLength(cls, header):
        """Given a header of HeaderLength bytes, calculate the size of this report
        """

        first_word, = unpack("<L", header[:4])

        length = (first_word >> 8)
        return length

    @classmethod
    def FromReadings(cls, uuid, readings, signature_method=auth_provider.HashOnlySHA256Signature, signer=None):
        """Generate an instance of the report format from a list of readings and a uuid

        Args:
            uuid (int): The uuid of the deviec that this report came from
            readings (list): A list of IOTileReading objects containing the data in the report
            signature_method (int): The method that should be used to sign the report (must be supported
                by an auth_provider)
            signer (AuthProvider): An optional preconfigured AuthProvider that should be used to sign this
                report.  If no AuthProvider is provided, the default ChainedAuthProvider is used.
        """

        lowest_id = IOTileReading.InvalidReadingID
        highest_id = IOTileReading.InvalidReadingID

        report_len = 20 + 16*len(readings) + 24
        len_low = report_len & 0xFF
        len_high = report_len >> 8

        unique_readings = [x.reading_id for x in readings if x.reading_id != IOTileReading.InvalidReadingID]
        if len(unique_readings) > 0:  
            lowest_id = min(unique_readings)
            highest_id = max(unique_readings)

        header = struct.pack("<BBHLLLBBH", cls.ReportType, len_low, len_high, uuid, 0, 0, signature_method, 0, 0xFFFF)
        header = bytearray(header)

        packed_readings = bytearray()

        for reading in readings:
            packed_reading = struct.pack("<HHLLL", reading.stream, 0, reading.reading_id, reading.raw_time, reading.value)
            packed_readings += bytearray(packed_reading)

        footer_stats = struct.pack("<LL", lowest_id, highest_id)
        signed_data = header + packed_readings + footer_stats

        if signer is None:
            signer = ChainedAuthProvider()

        try:
            signature = signer.sign(uuid, signature_method, signed_data)
        except NotFoundError:
            raise EnvironmentError("Could not sign report because no AuthProvider supported the requested signature method for the requested device", device_id=uuid, signature_method=signature_method)
        
        footer = struct.pack("16s", str(signature['signature'][:16]))
        footer = bytearray(footer)

        data = signed_data + footer
        return SignedListReport(data)

    def decode(self):
        """Decode this report into a list of readings
        """

        fmt, len_low, len_high, device_id, report_id, sent_timestamp, signature_flags, origin_streamer, streamer_selector = unpack("<BBHLLLBBH", self.raw_report[:20])

        assert fmt == 1
        length = (len_high << 8) | len_low

        self.origin = device_id
        self.report_id = report_id
        self.sent_timestamp = sent_timestamp
        self.origin_streamer = origin_streamer
        self.streamer_selector = streamer_selector
        self.signature_flags = signature_flags

        assert len(self.raw_report) == length

        remaining = self.raw_report[20:]
        assert len(remaining) >= 24
        readings = remaining[:-24]
        footer = remaining[-24:]

        lowest_id, highest_id, signature = unpack("<LL16s", footer)
        signature = bytearray(signature)

        signed_data = self.raw_report[:-16]
        signer = ChainedAuthProvider()

        try:
            verification = signer.verify(device_id, signature_flags, signed_data, signature)
            self.verified = verification['verified']
        except NotFoundError:
            pass

        self.signature = signature
        self.lowest_id = lowest_id
        self.highest_id = highest_id

        #Make sure this report has an integer number of readings
        assert (len(readings) % 16) == 0

        time_base = self.received_time - datetime.timedelta(seconds=sent_timestamp)
        parsed_readings = []

        for i in xrange(0, len(readings), 16):
            reading = readings[i:i+16]
            stream, _, reading_id, timestamp, value = unpack("<HHLLL", reading)

            parsed = IOTileReading(timestamp, stream, value, time_base=time_base, reading_id=reading_id)
            parsed_readings.append(parsed)

        #FIXME: attempt to validate the signature
        return parsed_readings

    def encode(self):
        """Turn this report into a serialized bytearray that could be decoded with a call to decode

        If we were generated from a binary report, just return that so that the signature remains intact,
        otherwise generate one and attempt to sign it 
        """

        if hasattr(self, 'raw_report'):
            return self.raw_report

        lowest_id = IOTileReading.InvalidReadingID
        highest_id = IOTileReading.InvalidReadingID

        report_len = 20 + 16*len(self.visible_readings) + 24
        len_low = report_len & 0xFF
        len_high = report_len >> 8

        if len(self.visible_readings) > 0:
            lowest_id = min([x.reading_id for x in self.visible_readings if x.reading_id != IOTileReading.InvalidReadingID])
            highest_id = max([x.reading_id for x in self.visible_readings if x.reading_id != IOTileReading.InvalidReadingID])

        header = struct.pack("<BBHLLLBBH", self.ReportType, len_low, len_high, self.origin, self.report_id, self.sent_timestamp, self.signature_flags, self.origin_streamer, self.streamer_selector)
        header = bytearray(header)

        readings = bytearray()

        for reading in self.visible_readings:
            packed_reading = struct.pack("<HHLLL", reading.stream, 0, reading.reading_id, reading.raw_time, reading.value)
            readings += bytearray(packed_reading)

        #FIXME: Actually calculate a footer here
        footer = struct.pack("<LL16s", lowest_id, highest_id, '\0'*16)
        footer = bytearray(footer)

        return header + readings + footer
