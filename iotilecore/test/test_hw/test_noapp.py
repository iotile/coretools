import unittest
import pytest
import os.path
import os
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.reports.signed_list_format import SignedListReport
from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *


@pytest.fixture
def simple_hw():
    hw = HardwareManager('virtual:no_app')
    yield hw
    hw.disconnect()

def test_finding_proxy(simple_hw):
    """Make sure NO APP is matched to a TileBusProxyObject
    """

    simple_hw.connect_direct(1)
    con = simple_hw.controller()

    assert con.ModuleName() == 'NO APP'
    con = simple_hw.get(8)
    assert con.ModuleName() == 'NO APP'
