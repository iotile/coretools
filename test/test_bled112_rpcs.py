import unittest
import threading
import serial
from test.util.mock_bled112 import MockBLED112
from test.util.ble_device import MockIOTileDevice
import test.util.dummy_serial
from iogateway.adapters.bled112.bled112 import BLED112Adapter
import time

class TestBLED112Connections(unittest.TestCase):
    """
    Test to make sure that the BLED112Adapter is properly handling disconnections
    """

    def setUp(self):
        self.old_serial = serial.Serial
        serial.Serial = test.util.dummy_serial.Serial
        self.adapter = MockBLED112(3)
        self.dev1 = MockIOTileDevice(100, "00:11:22:33:44:55", 3.3, 0)
        self.adapter.add_device(self.dev1)

        test.util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self.scanned_devices = []
        self.bled = BLED112Adapter('test', self._on_scan_callback, self._on_disconnect_callback)

    def tearDown(self):
        self.bled.stop()
        serial.Serial = self.old_serial

    def test_send_unhandled_rpc(self):
        result = self.bled.connect_sync(1, "00:11:22:33:44:55")
        result = self.bled.open_interface_sync(1, 'rpc')
        result = self.bled.send_rpc_sync(1, 120, 0xFFFF, bytearray([]), timeout=1.0)

        assert result['success'] is True
        assert result['status'] == 0xFF
        assert len(result['payload']) == 0

    def _on_scan_callback(self, ad_id, info, expiry):
        pass

    def _on_disconnect_callback(self, *args, **kwargs):
        pass
