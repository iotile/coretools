import unittest
import pytest
import os.path
import os
import struct
import logging
import sys
from iotile.mock.mock_iotile import MockIOTileDevice
from iotile.mock.mock_adapter import MockDeviceAdapter

class TestMockBLEBasic(unittest.TestCase):
    def setUp(self):
        self.dev = MockIOTileDevice(1, 'TestCN')
        self.adapter = MockDeviceAdapter()
        self.adapter.add_device('test', self.dev)

        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    def test_connect(self):
        res = self.adapter.connect_sync(1, 'test')
        assert res['success'] is True

    def test_connect_nothing(self):
        res = self.adapter.connect_sync(1, 'nothing')
        assert res['success'] is False

    def test_disconnect(self):
        res = self.adapter.connect_sync(1, 'test')
        assert res['success'] is True
        res = self.adapter.disconnect_sync(1)
        assert res['success'] is True

    def test_rpc(self):
        self.adapter.connect_sync(1, 'test')

        res = self.adapter.send_rpc_sync(1, 8, 4, '', 1.0) 
        assert len(res['payload']) == 6
        assert res['payload'] == 'TestCN'

    def test_advertisement(self):
        self.adapter.advertise()
