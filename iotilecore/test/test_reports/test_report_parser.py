import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.reports.parser import IOTileReportParser
from iotile.core.hw.reports.report import IOTileReading
from iotile.core.hw.reports.individual_format import IndividualReadingReport
from iotile.core.hw.reports.signed_list_format import SignedListReport
import struct
import datetime

def make_report(uuid, stream, value, timestamp, sent_time):
    return struct.pack("<BBHLLLL", 0, 0, stream, uuid, sent_time, timestamp, value)

def make_sequential(iotile_id, stream, num_readings, give_ids=False):
    readings = []

    for i in xrange(0, num_readings):
        if give_ids:
            reading = IOTileReading(i, stream, i, reading_id=i)
        else:
            reading = IOTileReading(i, stream, i)

        readings.append(reading)
        
    report = SignedListReport.FromReadings(iotile_id, readings)
    return report.encode()

class TestReportParser(unittest.TestCase):
    """
    Test to make sure that the ReportParser is working
    """

    def setUp(self):
        self.parser = IOTileReportParser()

    def tearDown(self):
        pass

    def test_basic_parsing(self):
        """Make sure we can parse a report
        """

        report_data = make_report(10, 1, 2, 3, 4)

        assert len(self.parser.reports) == 0
        self.parser.add_data(report_data)

        assert len(self.parser.reports) == 1
        assert isinstance(self.parser.reports[0], IndividualReadingReport)

    def test_basic_parsing_multiple(self):
        """Make sure we can parse multiple reports received at the same time
        """

        report_data1 = make_report(10, 1, 2, 3, 4)
        report_data2 = make_report(12, 1, 2, 3, 4)

        report_data = report_data1 + report_data2

        assert self.parser.state == self.parser.WaitingForReportType
        assert len(self.parser.reports) == 0
        self.parser.add_data(report_data)

        assert len(self.parser.reports) == 2
        assert isinstance(self.parser.reports[0], IndividualReadingReport)
        assert isinstance(self.parser.reports[1], IndividualReadingReport)
        assert self.parser.state == self.parser.WaitingForReportType

    def test_parsing_in_chunks(self):
        """Make sure that the state machine is properly updated with partial report reception
        """

        report_data1 = make_report(10, 1, 2, 3, 4)
        report_data2 = make_report(12, 1, 2, 3, 4)

        report_data = report_data1 + report_data2

        assert self.parser.state == self.parser.WaitingForReportType
        
        self.parser.add_data(report_data[:1])
        assert len(self.parser.reports) == 0
        assert self.parser.state == self.parser.WaitingForCompleteReport
        
        self.parser.add_data(report_data[1:19])
        assert self.parser.state == self.parser.WaitingForCompleteReport
        assert len(self.parser.reports) == 0

        self.parser.add_data(report_data[19:21])
        assert self.parser.state == self.parser.WaitingForCompleteReport
        assert len(self.parser.reports) == 1

        self.parser.add_data(report_data[21:])
        assert self.parser.state == self.parser.WaitingForReportType
        assert len(self.parser.reports) == 2

    def test_decoding_serialized_report(self):
        report_data1 = make_report(10, 1, 2, 3, 4)

        report = IndividualReadingReport(report_data1)
        ser = report.serialize()

        report2 = IOTileReportParser.DeserializeReport(ser)
        assert report2.origin == report.origin
        assert report2.received_time == report.received_time

    def test_mixed_types(self):
        """Make sure we can parse a mixture of different report types
        """

        report1 = make_report(10, 1, 2, 3, 4)
        report2 = make_sequential(1, 2, 11, True)

        self.parser.add_data(report1)
        self.parser.add_data(report2)
        self.parser.add_data(report1)

        assert len(self.parser.reports) == 3

        report1 = self.parser.reports[0]
        report2 = self.parser.reports[1]
        report3 = self.parser.reports[2]

        assert isinstance(report1, IndividualReadingReport)
        assert isinstance(report2, SignedListReport)
        assert isinstance(report3, IndividualReadingReport)

        assert len(report2.visible_readings) == 11
        assert self.parser.state == self.parser.WaitingForReportType

        #Make sure the readings in report2 are correct
        for i in xrange(0, len(report2.visible_readings)):
            reading = report2.visible_readings[i]

            assert reading.value == i
            assert reading.raw_time == i
            assert reading.reading_id == i
            assert reading.stream == 2
