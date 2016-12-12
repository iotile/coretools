import unittest
import pytest
import os.path
import os
import struct
import logging
import sys
from iotile.mock.mock_iotile import MockIOTileDevice
from iotile.mock.mock_adapter import MockDeviceAdapter
from iotile.core.hw.reports.individual_format import IndividualReadingReport
from iotile.core.hw.reports.report import IOTileReading
from iotilegateway.device import DeviceManager
from tornado.ioloop import IOLoop
import tornado.testing

class TestDeviceManager(tornado.testing.AsyncTestCase):
    def setUp(self):
        super(TestDeviceManager, self).setUp()

        self.dev = MockIOTileDevice(1, 'TestCN')
        self.dev.reports = [IndividualReadingReport.FromReadings(100, [IOTileReading(0, 1, 2)])]
        self.adapter = MockDeviceAdapter()
        self.adapter.add_device('test', self.dev)
        
        self.manager = DeviceManager(self.io_loop)
        self.manager.add_adapter(self.adapter)

    def tearDown(self):
        super(TestDeviceManager, self).tearDown()

    @tornado.testing.gen_test
    def test_connect_direct(self):
        """Make sure we can directly connect to a device
        """

        res = yield self.manager.connect_direct('0/test')
        assert res['success'] is True
    
    @tornado.testing.gen_test
    def test_send_rpc(self):
        res = yield self.manager.connect_direct('0/test')
        assert res['success'] is True

        conn_id = res['connection_id']

        res = yield self.manager.send_rpc(conn_id, 8, 0, 4, '', 1.0) 
        assert len(res['payload']) == 6
        assert res['payload'] == 'TestCN'
