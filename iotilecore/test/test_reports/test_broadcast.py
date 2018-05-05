"""Tests to ensure that BroadcastReport parsing and creation works."""

from iotile.core.hw.reports import BroadcastReport, IOTileReading, IOTileReportParser


def test_generation():
    """Make sure we can create a broadcast report, encode and decode it."""

    reading = IOTileReading(0, 0x5000, 100)

    report = BroadcastReport.FromReadings(1, [reading, reading])

    dec_report = BroadcastReport(report.encode())

    assert report.visible_readings == dec_report.visible_readings
    assert report.origin == dec_report.origin


def test_report_parser():
    """Make sure we can parse this report in an IOTileReportParser."""

    reading = IOTileReading(0, 0x5000, 100)
    report = BroadcastReport.FromReadings(1, [reading, reading])
    encoded = report.encode()

    parser = IOTileReportParser()
    parser.add_data(encoded)

    assert len(parser.reports) == 1
    assert parser.reports[0].visible_readings == report.visible_readings
