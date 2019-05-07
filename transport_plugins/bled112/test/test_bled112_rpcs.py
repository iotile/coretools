import unittest
import threading
import serial
import pytest
from util.mock_bled112 import MockBLED112
from iotile.mock.mock_ble import MockBLEDevice
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice
import util.dummy_serial
from iotile_transport_bled112.bled112 import BLED112Adapter
import time

class TestBLED112RPCs(unittest.TestCase):
    """
    Test to make sure that the BLED112Adapter is properly handling RPCs
    """

    def setUp(self):
        self.old_serial = serial.Serial
        serial.Serial = util.dummy_serial.Serial
        self.adapter = MockBLED112(3)
        self.dev1 = SimpleVirtualDevice(100, 'TestCN')
        self.dev1_ble = MockBLEDevice("00:11:22:33:44:55", self.dev1)
        self.adapter.add_device(self.dev1_ble)

        util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self.scanned_devices = []
        self.bled = BLED112Adapter('test', self._on_scan_callback, self._on_disconnect_callback, stop_check_interval=0.01)
        self._current = None
        self._total = None

    def tearDown(self):
        self.bled.stop_sync()
        serial.Serial = self.old_serial

    def test_send_unhandled_rpc(self):
        result = self.bled.connect_sync(1, "00:11:22:33:44:55")
        result = self.bled.open_interface_sync(1, 'rpc')

        result = self.bled.send_rpc_sync(1, 120, 0xFFFF, bytearray([]), timeout=1.0)

        assert result['success'] is True
        assert result['status'] == 0xFF
        assert len(result['payload']) == 0

    def test_send_script(self):
        result = self.bled.connect_sync(1, "00:11:22:33:44:55")
        assert result['success'] is True

        result = self.bled.open_interface_sync(1, 'script')
        assert result['success'] is True

        script = b'\xab'*1027
        result = self.bled.send_script_sync(1, script, self._script_progress)

        assert len(self.dev1.script) == len(script)
        assert self.dev1.script == script
        assert result['success'] is True
        assert self._current == self._total
        assert self._total == (1027 // 20)

    def _script_progress(self, current, total):
        self._current = current
        self._total = total

    def _on_scan_callback(self, ad_id, info, expiry):
        pass

    def _on_disconnect_callback(self, *args, **kwargs):
        pass
