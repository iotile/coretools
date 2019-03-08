import unittest
import threading
import serial
from util.mock_bled112 import MockBLED112
from iotile.mock.mock_ble import MockBLEDevice
from iotile.mock.mock_iotile import MockIOTileDevice
import util.dummy_serial
from iotile_transport_bled112.bled112 import BLED112Adapter

class TestBLED112AdapterPassive(unittest.TestCase):
    """
    Test to make sure that the BLED112Adapter is working correctly
    """

    def setUp(self):
        self.old_serial = serial.Serial
        serial.Serial = util.dummy_serial.Serial
        self.adapter = MockBLED112(3)

        self.dev1 = MockIOTileDevice(100, 'TestCN')
        self.dev1_ble = MockBLEDevice("00:11:22:33:44:55", self.dev1)
        self.adapter.add_device(self.dev1_ble)

        util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self._scanned_devices_seen = threading.Event()
        self.num_scanned_devices = 0
        self.scanned_devices = []
        self.bled = BLED112Adapter('test', self._on_scan_callback, self._on_disconnect_callback, stop_check_interval=0.01)

    def tearDown(self):
        self.bled.stop_sync()
        serial.Serial = self.old_serial

    def test_basic_init(self):
        """Test that we initialize correctly and the bled112 comes up scanning
        """

        assert self.bled.scanning

    def _on_scan_callback(self, ad_id, info, expiry):
        self.num_scanned_devices += 1
        self.scanned_devices.append(info)
        self._scanned_devices_seen.set()

    def _on_disconnect_callback(self, *args, **kwargs):
        pass

    def test_scanning(self):
        self._scanned_devices_seen.wait(timeout=1.0)
        assert self.num_scanned_devices == 1
        assert 'voltage' not in self.scanned_devices[0]
