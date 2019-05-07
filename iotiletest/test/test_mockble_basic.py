import struct
import logging
import sys
import unittest
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice
from iotile.mock.mock_ble import MockBLEDevice

class TestMockBLEBasic(unittest.TestCase):
    def setUp(self):
        self.dev = SimpleVirtualDevice(1, 'TestCN')
        self.ble = MockBLEDevice("AA:BB:CC:DD:EE:FF", self.dev)
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    def tearDown(self):
        pass

    def test_basic_functionality(self):
        """Make sure that things are setup right
        """

        assert self.ble.notifications_enabled(self.ble.TBReceiveHeaderChar) is False
        assert self.ble.notifications_enabled(self.ble.TBReceivePayloadChar) is False
        assert self.ble.notifications_enabled(self.ble.TBStreamingChar) is False

    def test_calling_invalid_rpc(self):
        """Make sure that basically calling an RPC works
        """

        header = struct.pack("<BBBBB", 0, 0, 0xFF, 0xFF, 127)

        success, notif = self.ble._handle_write(self.ble.TBSendPayloadChar, b"")
        assert success is True
        assert len(notif) == 0

        success, notif = self.ble._handle_write(self.ble.TBSendHeaderChar, header)
        assert success is True
        assert len(notif) == 1

        char_id, resp_header = notif[0]
        assert self.ble.find_uuid(char_id)[0] == self.ble.TBReceiveHeaderChar

        status, _, resp_len, _ = struct.unpack("<BBBB", resp_header)
        assert status == 0xFF
        assert resp_len == 0

    def test_calling_valid_rpc(self):
        """Make sure that calling a valid RPC with a payload works
        """

        header = struct.pack("<BBBBB", 0, 0, 0x04, 0x00, 8)

        success, notif = self.ble._handle_write(self.ble.TBSendPayloadChar, b"")
        assert success is True
        assert len(notif) == 0

        success, notif = self.ble._handle_write(self.ble.TBSendHeaderChar, header)
        assert success is True
        assert len(notif) == 2

        char_id, resp_header = notif[0]
        assert self.ble.find_uuid(char_id)[0] == self.ble.TBReceiveHeaderChar

        char_id, resp_payload = notif[1]
        assert self.ble.find_uuid(char_id)[0] == self.ble.TBReceivePayloadChar
