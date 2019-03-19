"""Tests of UTCAssigner functionality."""

import os
import re
import datetime
import pytest
import dateutil.parser
from iotile.core.hw.reports import UTCAssigner, SignedListReport, IOTileReportParser


def load_report(filename, received_regex=None):
    """Load a SignedListReport from a file.

    If received_regex is not None, it must be a regular express pattern string
    that will be used to extract the report's received timestmap from the
    filename.

    The first match group in the pattern must be the received time and it
    should be in isoformat except that the time part may be separated by `-`
    instead of `:` so that it can be used as part of a path.
    """

    base_dir = os.path.join(os.path.dirname(__file__), 'data')
    file_path = os.path.join(base_dir, filename)

    with open(file_path, "rb") as infile:
        data = infile.read()

    parser = IOTileReportParser()
    parser.add_data(data)

    assert len(parser.reports) == 1

    report = parser.reports[0]
    assert isinstance(report, SignedListReport)

    if received_regex is not None:
        result = re.match(received_regex, filename)
        assert result is not None

        datetime_string = result.group(1)

        if 'T' in datetime_string:
            date_part, _, time_part = datetime_string.partition('T')
            time_part = time_part.replace('-', ':')
            datetime_string = "T".join([date_part, time_part])

        datetime_obj = dateutil.parser.parse(datetime_string, fuzzy=True, ignoretz=True)
        report.received_time = datetime_obj

    return report


def compare_fixed_report(fixed, ref_filename):
    """Compare a fixed report with a reference file that should match."""

    base_dir = os.path.join(os.path.dirname(__file__), 'data')
    file_path = os.path.join(base_dir, ref_filename)

    with open(file_path, "r") as infile:
        ref_lines = [x.strip() for x in infile.readlines() if x.strip() != ""]

    assert len(fixed.visible_readings) == len(ref_lines)

    for reading, ref_string in zip(fixed.visible_readings, ref_lines):
        assert str(reading) == ref_string


@pytest.fixture(scope="module")
def assigner():
    """Create a loaded utc assigner."""

    regex = r'^report_[0-9]_(.*)\.bin$'
    report0 = load_report('report_0_2019-03-04T19-37-28.504446.bin', regex)
    report1 = load_report('report_1_2019-03-04T19-37-29.953927.bin', regex)
    report2 = load_report('report_2_2019-03-04T19-37-30.377019.bin', regex)

    assigner = UTCAssigner()
    assigner.anchor_stream(0x0E00, converter="epoch")
    assigner.anchor_stream(0x0E01, converter="epoch")

    assigner.add_report(report0)
    assigner.add_report(report1)
    assigner.add_report(report2)

    return assigner


def test_basic_utcassigner(assigner):
    """Make sure we are able to load in reports."""

    assert assigner.id_range() == (16, 21962)


def test_anchor_assignments(assigner):
    """Make sure we correctly assign UTC when it exists in a report.

    We know these anchor points exist in the loaded reports and have UTC
    assignments already.
    """

    start = assigner.assign_utc(0x0000001C, uptime=0xb3a)
    assert start is not None
    assert start.epoch_value == 0x5BEDC6FA
    assert start.exact
    assert not start.crossed_break

    end = assigner.assign_utc(0x000055BE, uptime=0x2d)
    assert end is not None
    assert end.epoch_value == 0x5C79ABE9
    assert end.exact
    assert not end.crossed_break

    report = assigner.assign_utc(0x55CA, uptime=None)
    assert report is not None
    assert report.utc == datetime.datetime(2019, 3, 4, 19, 37, 30, 377019)
    assert report.exact
    assert not report.crossed_break


def test_bidirectional_fixes(assigner):
    """Make sure we do proper bidirectional fixes."""

    left = assigner.assign_utc(0x000055B9, uptime=0x00620D90, prefer="before")
    right = assigner.assign_utc(0x000055B9, uptime=0x00620D90, prefer="after")

    assert left is not None
    assert right is not None
    assert left.utc == right.utc
    assert left.exact
    assert right.exact

    # The reading time should be the start timestamp + the reading uptime - start uptime
    assert left.epoch_value == 0x5BEDC6FA + 0x00620D90 - 0x00000B3A
    assert left.epoch_value == right.epoch_value

    # Make sure we properly handle data before any exact anchors
    first = assigner.assign_utc(0x10, uptime=4, prefer="before")
    assert first.utc == datetime.datetime(2018, 11, 15, 18, 32, 26)
    assert first.exact is False

def test_whole_report_fixing(assigner):
    """Make sure we can fix entire reports."""

    regex = r'^report_[0-9]_(.*)\.bin$'
    report0 = load_report('report_0_2019-03-04T19-37-28.504446.bin', regex)
    report1 = load_report('report_1_2019-03-04T19-37-29.953927.bin', regex)
    report2 = load_report('report_2_2019-03-04T19-37-30.377019.bin', regex)

    fixed0 = assigner.fix_report(report0)
    fixed1 = assigner.fix_report(report1)
    fixed2 = assigner.fix_report(report2)

    #print("\nReport 0")
    #for reading in fixed0.visible_readings:
    #    print(reading)

    #print("\nReport 1")
    #for reading in fixed1.visible_readings:
    #    print(reading)

    #print("\nReport 2")
    #for reading in fixed2.visible_readings:
    #    print(reading)

    compare_fixed_report(fixed0, 'report_0_fixed.txt')
    compare_fixed_report(fixed1, 'report_1_fixed.txt')
    compare_fixed_report(fixed2, 'report_2_fixed.txt')
