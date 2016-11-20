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
        self.adapter.add_device(MockIOTileDevice(100, "00:11:22:33:44:55", 3.3, 0))

        test.util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self._connected = threading.Event()
        self.scanned_devices = []
        self.bled = BLED112Adapter('test', self._on_scan_callback, self._on_disconnect_callback)

    def tearDown(self):
        self.bled.stop()
        serial.Serial = self.old_serial

    def test_connect_but_noresponse(self):
        start = time.time()
        self.bled.connect("00:11:22:33:44:55", 0, self._on_connection)
        self._connected.wait()
        end = time.time()

        print end - start
        assert self._result

    def _on_connection(self, conn_id, result, value):
        self._connected.set()

        self._result = result
        self._conn_id = conn_id
        self._value = value

    def _on_scan_callback(self, ad_id, info, expiry):
        pass

    def _on_disconnect_callback(self, *args, **kwargs):
        pass
