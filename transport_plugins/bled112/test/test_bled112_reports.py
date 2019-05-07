import unittest
import threading
import serial
import pytest
from util.mock_bled112 import MockBLED112
from iotile.mock.mock_ble import MockBLEDevice
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice
import util.dummy_serial
from iotile_transport_bled112.bled112 import BLED112Adapter
from iotile.core.hw.reports import IOTileReading, IndividualReadingReport
import time
import logging
import sys

class TestBLED112Reports(unittest.TestCase):
    """
    Test to make sure that the BLED112Adapter is properly handling reports
    """

    def setUp(self):
        self.old_serial = serial.Serial
        serial.Serial = util.dummy_serial.Serial
        self.adapter = MockBLED112(3)
        self.dev1 = SimpleVirtualDevice(100, 'TestCN')
        self.dev1_ble = MockBLEDevice("00:11:22:33:44:55", self.dev1)
        self.adapter.add_device(self.dev1_ble)

        self.dev1.reports = [IndividualReadingReport.FromReadings(100, [IOTileReading(0, 1, 2)])]
        self._reports_received = threading.Event()

        logging.basicConfig(level=logging.INFO, stream=sys.stdout)

        util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self.scanned_devices = []
        self.bled = BLED112Adapter('test', self._on_scan_callback, self._on_disconnect_callback, passive=False, stop_check_interval=0.01)
        self.bled.add_callback('on_report', self._on_report_callback)
        self.reports = []

    def tearDown(self):
        self.bled.stop_sync()
        serial.Serial = self.old_serial

    def test_receiving_reports(self):
        result = self.bled.connect_sync(1, "00:11:22:33:44:55")
        assert result['success'] is True

        assert len(self.reports) == 0
        result = self.bled.open_interface_sync(1, 'streaming')
        assert result['success'] is True

        self._reports_received.wait(1.0)
        assert len(self.reports) == 1

    def _on_scan_callback(self, ad_id, info, expiry):
        pass

    def _on_disconnect_callback(self, *args, **kwargs):
        pass

    def _on_report_callback(self, conn_id, report):
        self.reports.append(report)
        self._reports_received.set()

    def test_broadcast(self):
        """Make sure we can get broadcast packets."""

        self.dev1_ble.broadcast_reading = IOTileReading(1, 0x1000, 100)

        self.bled.stop_scan()
        assert self.adapter.scanning is False
        self._reports_received.clear()
        self.bled.start_scan(True)

        self._reports_received.wait(1.0)
        assert len(self.reports) == 1

        reading = self.reports[0].visible_readings[0]
        assert reading.stream == 0x1000
        assert reading.raw_time == 1
        assert reading.value == 100

        self._reports_received.clear()

        self.adapter.advertise()
        self._reports_received.wait(1.0)
        assert len(self.reports) == 1

        reading = self.reports[0].visible_readings[0]
        assert reading.stream == 0x1000
        assert reading.raw_time == 1
        assert reading.value == 100
