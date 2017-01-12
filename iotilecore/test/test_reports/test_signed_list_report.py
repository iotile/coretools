import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.reports.signed_list_format import SignedListReport
from iotile.core.hw.reports.report import IOTileReading
import struct
import datetime

def make_sequential(iotile_id, stream, num_readings, give_ids=False):
    readings = []

    for i in xrange(0, num_readings):
        if give_ids:
            reading = IOTileReading(i, stream, i, reading_id=i)
        else:
            reading = IOTileReading(i, stream, i)

        readings.append(reading)
        
    report = SignedListReport.FromReadings(iotile_id, readings)
    return report

def test_basic_parsing():
    """Make sure we can decode a signed report
    """

    report = make_sequential(1, 0x1000, 10)
    encoded = report.encode()

    report2 = SignedListReport(encoded)

    assert len(report.visible_readings) == 10
    assert len(report2.visible_readings) == 10

    for i, reading in enumerate(report.visible_readings):
        assert reading == report2.visible_readings[i]

def test_footer_calculation():
    """
    """

    report1 = make_sequential(1, 0x1000, 10, give_ids=False)
    report2 = make_sequential(1, 0x1000, 10, give_ids=True)

    assert report1.lowest_id == 0xFFFFFFFF
    assert report1.highest_id == 0xFFFFFFFF

    assert report2.lowest_id == 0
    assert report2.highest_id == 9
