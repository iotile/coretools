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
    conf_file = os.path.join(os.path.dirname(__file__), 'report_test_config_hash.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:report_test@%s' % conf_file)
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

def test_config_file(conf2_report_hw, monkeypatch):
    """Make sure we can pass a config dict
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
