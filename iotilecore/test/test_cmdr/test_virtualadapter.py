# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotile.core.hw.hwmanager import HardwareManager
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

def test_basic(simple_hw):
    simple_hw.connect_direct('1')

