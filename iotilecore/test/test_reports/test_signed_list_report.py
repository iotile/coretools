import unittest
import os
import pytest
from iotile.core.exceptions import ExternalError
from iotile.core.hw.reports.signed_list_format import SignedListReport
from iotile.core.hw.reports.report import IOTileReading


def make_sequential(iotile_id, stream, num_readings, give_ids=False, root_key=0):
    readings = []

    for i in range(0, num_readings):
        if give_ids:
            reading = IOTileReading(i, stream, i, reading_id=i+1)
        else:
            reading = IOTileReading(i, stream, i)

        readings.append(reading)

    report = SignedListReport.FromReadings(iotile_id, readings, root_key=root_key)
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

    assert report2.verified is True
    assert report.verified is True
    assert report.signature_flags == 0

def test_footer_calculation():
    """
    """

    report1 = make_sequential(1, 0x1000, 10, give_ids=False)
    report2 = make_sequential(1, 0x1000, 10, give_ids=True)

    assert report1.lowest_id == 0
    assert report1.highest_id == 0

    assert report2.lowest_id == 1
    assert report2.highest_id == 10

def test_userkey_signing(monkeypatch):
    """Make sure we can sign and encrypt reports."""

    monkeypatch.setenv('USER_KEY_00000002', '0000000000000000000000000000000000000000000000000000000000000000')

    with pytest.raises(ExternalError):
        report1 = make_sequential(1, 0x1000, 10, give_ids=True, root_key=1)

    report1 = make_sequential(2, 0x1000, 10, give_ids=True, root_key=1)

    encoded = report1.encode()
    report2 = SignedListReport(encoded)

    assert report1.signature_flags == 1
    assert report2.signature_flags == 1
    assert report1.verified
    assert report1.encrypted
    assert report2.verified
    assert report2.encrypted

    assert len(report2.visible_readings) == 10

    for i, reading in enumerate(report2.visible_readings):
        assert reading.value == i
        assert reading.reading_id == (i + 1)


def test_str_conversion():
    """Make sure str conversion works."""

    report = make_sequential(1, 0x1000, 10, give_ids=True)

    str_report = str(report)
    assert str_report == 'IOTile Report (length: 204, visible readings: 10, visible events: 0, verified and not encrypted)'
