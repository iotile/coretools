import unittest
import threading
import serial
from util.mock_bled112 import MockBLED112
from iotile.mock.mock_ble import MockBLEDevice
from iotile.mock.mock_iotile import MockIOTileDevice
import util.dummy_serial
from iotile_transport_bled112.bled112 import BLED112Adapter
import time

class TestBLED112Connections(unittest.TestCase):
    """
    Test to make sure that the BLED112Adapter is properly handling disconnections
    """

    def setUp(self):
        self.old_serial = serial.Serial
        serial.Serial = util.dummy_serial.Serial
        self.adapter = MockBLED112(3)
        self.dev1 = MockIOTileDevice(100, 'TestCN')
        self.dev1_ble = MockBLEDevice("00:11:22:33:44:55", self.dev1)
        self.adapter.add_device(self.dev1_ble)

        util.dummy_serial.RESPONSE_GENERATOR = self.adapter.generate_response

        self._connected = threading.Event()
        self._rpcs_enabled = threading.Event()
        self.scanned_devices = []
        self.bled = BLED112Adapter('test', self._on_scan_callback, self._on_disconnect_callback, stop_check_interval=0.01)

    def tearDown(self):
        self.bled.stop_sync()
        serial.Serial = self.old_serial

    def test_connect_but_nodevice(self):
        start = time.time()
        self.bled.connect_async(0, "00:11:22:33:44:56", self._on_connection)
        self._connected.wait()
        end = time.time()

        assert self._conn_id == 0
        assert self._result is False

    def test_connection_succeeds(self):
        start = time.time()
        self.bled.connect_async(1, "00:11:22:33:44:55", self._on_connection)
        self._connected.wait()
        end = time.time()

        print self.bled._connections[0]['services']

        assert self._conn_id == 1
        assert self._result is True

    def test_disconnect_nodevice(self):
        result = self.bled.disconnect_sync(1)
        assert result['success'] is False

    def test_disconnect_device(self):
        result = self.bled.connect_sync(1, "00:11:22:33:44:55")
        assert result['success'] is True

        result = self.bled.disconnect_sync(1)
        assert result['success'] is True

    def test_enable_rpcs(self):
        result = self.bled.connect_sync(1, "00:11:22:33:44:55")
        assert result['success'] is True

        assert not self.dev1_ble.notifications_enabled(self.dev1_ble.TBReceiveHeaderChar)
        assert not self.dev1_ble.notifications_enabled(self.dev1_ble.TBReceivePayloadChar)

        result = self.bled.open_interface_sync(1, 'rpc')
        assert result['success'] is True

        assert self.dev1_ble.notifications_enabled(self.dev1_ble.TBReceiveHeaderChar)
        assert self.dev1_ble.notifications_enabled(self.dev1_ble.TBReceivePayloadChar)

    def _on_connection(self, conn_id, adapter_id, result, value):
        self._result = result
        self._conn_id = conn_id
        self._value = value

        self._connected.set()

    def _on_rpcs_enabled(self, conn_id, result, value):
        self._result = result
        self._conn_id = conn_id
        self._value = value

        self._rpcs_enabled.set()

    def _on_scan_callback(self, ad_id, info, expiry):
        pass

    def _on_disconnect_callback(self, *args, **kwargs):
        pass
