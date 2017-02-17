from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.reports.signed_list_format import SignedListReport
from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *
import unittest
import pytest
import os.path
import os

@pytest.fixture
def conf_hex_tracing():
    conf_file = os.path.join(os.path.dirname(__file__), 'tracing_hex_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:tracing_test@%s' % conf_file)
    hw.connect_direct('1')
    yield hw

    hw.disconnect()

@pytest.fixture
def conf_ascii_tracing():
    conf_file = os.path.join(os.path.dirname(__file__), 'tracing_ascii_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    hw = HardwareManager('virtual:tracing_test@%s' % conf_file)
    hw.connect_direct('1')
    yield hw

    hw.disconnect()

def test_hex_tracing(conf_hex_tracing):
    """Make sure that we can stream binary data that is not ascii printable
    """

    hw = conf_hex_tracing

    assert hw.dump_trace('raw') == ""
    assert hw.dump_trace('hex') == ""

    hw.enable_tracing()

    assert hw.dump_trace('hex') == 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890'

def test_ascii_tracing(conf_ascii_tracing):
    """Make sure we can stream ascii data that is not encoded in any way
    """

    hw = conf_ascii_tracing

    assert hw.dump_trace('raw') == ""
    assert hw.dump_trace('hex') == ""

    hw.enable_tracing()

    assert hw.dump_trace('raw') == 'hello this is an acsii data stream that is somewhat long'
