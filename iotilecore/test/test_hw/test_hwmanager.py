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

class TestHardwareManager(unittest.TestCase):
    """
    Test to make sure that the HardwareManager is working
    """

    def setUp(self):
        self.hw = HardwareManager('none')

    def tearDown(self):
        pass

    def test_unknown_module(self):
        with pytest.raises(UnknownModuleTypeError):
            self.hw._create_proxy('UnknownTileBusModule', 8)
