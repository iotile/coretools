"""If there are two bled112 dongles on this computer attempt to setup a loopback test

We will serve a virtual device over one bled112 and connect to it with the other bled112
"""

import pytest
import unittest
import subprocess
from iotile_transport_bled112.bled112 import BLED112Adapter
from iotile.core.hw.hwmanager import HardwareManager
import time
import signal

can_loopback = len(BLED112Adapter.find_bled112_devices()) >= 2

@pytest.mark.skipif(True, reason='(loopback not finished yet)You need two BLED112 adapters for loopback tests')
class TestBLED112Loopback(unittest.TestCase):
    def setUp(self):
        self.vdev = subprocess.Popen(['virtual_device', 'bled112', 'report_test'])

        bleds = BLED112Adapter.find_bled112_devices()
        print(bleds)
        self.hw = HardwareManager(port='bled112:{}'.format(bleds[1]))

    def tearDown(self):
        self.hw.close()
        self.vdev.terminate()

    def test_loopback(self):
        time.sleep(2)
        print(self.hw.scan())
        self.hw.connect(1)
        con = self.hw.controller()
        assert con.ModuleName() == 'Simple'

        self.hw.enable_streaming()
        assert self.hw.count_reports() == 11
