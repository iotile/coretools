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
import json
import unittest
import pytest
import os.path
import os

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
    conf_file = os.path.join(os.path.dirname(__file__), 'report_zero_length.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:report_test@%s' % conf_file)
    yield hw

    hw.disconnect()

@pytest.fixture(scope="function")
def inline_config_report_hw(tmpdir):
    config = {
        "device": {
            "iotile_id": "1",
            "reading_start": 0,
            "num_readings": 0,
            "stream_id": "5001",
            "format": "signed_list",
            "report_length": 0,
            "signing_method": 0
        }
    }

    config_obj = tmpdir.join("config.json")
    config_obj.write(json.dumps(config))
    config_path = str(config_obj)

    hw = HardwareManager(port="virtual:report_test@%s" % config_path)
    hw.connect(1)

    yield hw

    hw.disconnect()

def test_config_file(conf_report_hw):
    """Make sure zero length reports work
    """

    conf_report_hw.connect_direct('2')
    conf_report_hw.enable_streaming()

    assert conf_report_hw.count_reports() == 1
    rep1 = [x for x in conf_report_hw.iter_reports()][0]

    assert rep1.verified == 1
    assert len(rep1.visible_readings) == 0

def test_invalid_length_combo():
    """Make sure invalid length combinations throw an exception
    """

    conf_file = os.path.join(os.path.dirname(__file__), 'report_length_invalid.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    with pytest.raises(ArgumentError):
        hw = HardwareManager('virtual:report_test@%s' % conf_file)

def test_report_device_rpc(inline_config_report_hw):
    hw = inline_config_report_hw
    proxy = hw.controller()

    index = 1
    value = 99
    force = False

    error = proxy.acknowledge_streamer(index, force, value)
    assert error == 0

    result = proxy.query_streamer(index)
    assert result["ack"] == value
