# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.reports.signed_list_format import SignedListReport
from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *
import pytest
import os.path
import os
import time


@pytest.fixture
def simple_hw():
    hw = HardwareManager('virtual:simple')
    yield hw

    hw.disconnect()


@pytest.fixture
def report_hw():
    hw = HardwareManager('virtual:report_test')
    yield hw

    hw.disconnect()


@pytest.fixture
def conf_report_hw():
    conf_file = os.path.join(os.path.dirname(__file__), 'report_test_config_hash.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:report_test@%s' % conf_file)
    yield hw

    hw.disconnect()


@pytest.fixture
def realtime_hw():
    conf_file = os.path.join(os.path.dirname(__file__), 'fast_realtime_test.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:realtime_test@%s' % conf_file)
    yield hw

    hw.disconnect()

@pytest.fixture
def realtime_scan_hw():
    conf_file = os.path.join(os.path.dirname(__file__), 'fast_realtime_test.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:realtime_test@%s' % conf_file)
    yield hw

    hw.disconnect()

@pytest.fixture
def tile_based():
    conf_file = os.path.join(os.path.dirname(__file__), 'tile_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:tile_based@%s' % conf_file)
    yield hw

    hw.disconnect()

@pytest.fixture
def tracer_hw():
    conf_file = os.path.join(os.path.dirname(__file__), 'fast_realtime_trace.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:realtime_test@%s' % conf_file)
    yield hw

    hw.disconnect()


@pytest.fixture
def conf2_report_hw():
    conf_file = os.path.join(os.path.dirname(__file__), 'report_test_config_signed.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:report_test@%s' % conf_file)
    yield hw

    hw.disconnect()

def test_basic(simple_hw):
    simple_hw.connect_direct('1')


def test_report(report_hw):
    report_hw.connect_direct('1')
    report_hw.enable_streaming()
    assert report_hw.count_reports() == 100


def test_config_file(conf_report_hw):
    """Make sure we can pass a config dict
    """

    conf_report_hw.connect_direct('2')
    conf_report_hw.enable_streaming()
    assert conf_report_hw.count_reports() == 11


def test_config_file2(conf2_report_hw, monkeypatch):
    """Make sure we can sign reports
    """

    monkeypatch.setenv('USER_KEY_00000002', '0000000000000000000000000000000000000000000000000000000000000000')

    conf2_report_hw.connect_direct('2')
    conf2_report_hw.enable_streaming()

    assert conf2_report_hw.count_reports() == 11

    for report in conf2_report_hw.iter_reports():
        assert report.verified
        assert report.signature_flags == 1
        assert report.lowest_id >= 1
        assert report.highest_id > report.lowest_id
        assert isinstance(report, SignedListReport)


def test_realtime_streaming(realtime_hw):
    """Make sure we properly support streaming asynchronously
    """

    realtime_hw.connect_direct('1')
    realtime_hw.enable_streaming()

    reports = realtime_hw.wait_reports(10)

    stream1 = [x for x in reports if x.visible_readings[0].stream == 0x100a]
    stream2 = [x for x in reports if x.visible_readings[0].stream == 0x5001]

    assert len(stream1) != 0
    assert len(stream2) != 0

    assert stream1[0].visible_readings[0].value == 200
    assert stream2[0].visible_readings[0].value == 100


def test_realtime_tracing(tracer_hw):
    """Make sure we properly support tracing data asynchronously
    """

    tracer_hw.connect_direct('1')
    tracer_hw.enable_tracing()

    time.sleep(.1)

    trace_data = tracer_hw.dump_trace('raw')

    assert len(trace_data) > 0
    words = trace_data.split(' ')

    wrong_data = [x for x in words if (x != 'hello' and x != 'goodbye' and x != '')]
    assert len(wrong_data) == 0


def test_virtual_scan(realtime_scan_hw):
    """Make sure we can scan for virtual devices and connect directly without connect_direct
    """
    devices = realtime_scan_hw.scan()

    assert len(devices) > 0
    realtime_scan_hw.connect('1')


def test_tilebased_device(tile_based):
    """Make sure we can interact with tile based virtual devices."""

    hw = tile_based

    hw.connect(1)
    con = hw.controller()
    tile1 = hw.get(11)

    assert con.add(1, 2) == 3
    con.count()

    assert tile1.add(3, 5) == 8
    tile1.count()
