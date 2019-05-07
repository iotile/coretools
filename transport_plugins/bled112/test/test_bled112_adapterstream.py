import unittest
import threading
import serial
import pytest
from util.mock_bled112 import MockBLED112
from iotile.mock.mock_ble import MockBLEDevice
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice
import util.dummy_serial
from iotile_transport_bled112.bled112 import BLED112Adapter
from iotile.core.hw.reports.individual_format import IndividualReadingReport
from iotile.core.hw.reports.report import IOTileReading
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError, HardwareError
import time
import logging
import sys

class TestBLED112AdapterStream(unittest.TestCase):
    """
    Test to make sure that the BLED112AdapterStream is working properly

    Test that it can connect, connect_direct, send rpcs and get reports
    """

    def setUp(self):
        self.old_serial = serial.Serial
        serial.Serial = util.dummy_serial.Serial
        self.adapter = MockBLED112(3)
        self.dev1 = SimpleVirtualDevice(100, 'TestCN')
        self.dev1_ble = MockBLEDevice("00:11:22:33:44:55", self.dev1)
        self.adapter.add_device(self.dev1_ble)
        util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self.dev1.reports = [IndividualReadingReport.FromReadings(100, [IOTileReading(0, 1, 2)])]
        self._reports_received = threading.Event()

        logging.basicConfig(level=logging.INFO, stream=sys.stdout)

        self.scanned_devices = []

        self.hw = HardwareManager(port='bled112:test')

    def tearDown(self):
        self.hw.close()

    def test_connect_direct(self):
        self.hw.connect_direct("00:11:22:33:44:55")

    def test_connect_nonexistent(self):
        with pytest.raises(HardwareError):
            self.hw.connect_direct("00:11:22:33:44:56")

    def test_connect_badconnstring(self):
        with pytest.raises(HardwareError):
            self.hw.connect_direct("00:11:22:33:44:5L")

    def test_report_streaming(self):
        self.hw.connect_direct("00:11:22:33:44:55")

        assert self.hw.count_reports() == 0
        self.hw.enable_streaming()
        time.sleep(0.2) #Wait for report callback to happen from bled112 thread
        assert self.hw.count_reports() == 1

