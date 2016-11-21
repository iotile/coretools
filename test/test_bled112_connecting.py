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

    def test_connect_but_nodevice(self):
        start = time.time()
        self.bled.connect("00:11:22:33:44:56", 0, self._on_connection)
        self._connected.wait()
        end = time.time()

        assert self._conn_id == 0
        assert self._result is False

    def test_connection_succeeds(self):
        start = time.time()
        self.bled.connect("00:11:22:33:44:55", 1, self._on_connection)
        self._connected.wait()
        end = time.time()

        assert self._conn_id == 1
        assert self._result is True

    def test_enable_rpcs(self):
        self.bled.connect("00:11:22:33:44:55", 1, self._on_connection)
        self._connected.wait()

        self._connected.clear()
        self.bled.enable_rpcs(1, self._on_connection)
        self._connected.wait()

        assert self._result is True

    def _on_connection(self, conn_id, result, value):
        self._result = result
        self._conn_id = conn_id
        self._value = value

        self._connected.set()

    def _on_scan_callback(self, ad_id, info, expiry):
        pass

    def _on_disconnect_callback(self, *args, **kwargs):
        pass
