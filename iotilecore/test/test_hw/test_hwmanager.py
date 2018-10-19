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
from iotile.core.utilities.gid import uuid_to_slug

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

    def test_uuid_to_slug(kvstore):
        """Test UUID to DeviceSlug
        """

        with pytest.raises(ArgumentError):
            uuid_to_slug('a')

        assert uuid_to_slug(1) == 'd--0000-0000-0000-0001'
        assert uuid_to_slug(640000) == 'd--0000-0000-0009-c400'

