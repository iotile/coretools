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
import threading
from tornado.ioloop import IOLoop
import tornado.gen
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
        self.manager.register_monitor(1, ['report'], self.on_report)
        self.reports = []
        self.reports_received = threading.Event()

    def tearDown(self):
        super(TestDeviceManager, self).tearDown()

    def on_report(self, dev_uuid, event_name, report):
        """Callback triggered when a report is received from a device on a device adapter
        """

        self.reports.append(report)
        self.reports_received.set()

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

    def test_monitors(self):
        mon_id = self.manager.register_monitor(10, ['report'], lambda x,y: x)
        self.manager.adjust_monitor(mon_id, add_events=['connection'], remove_events=['report'])
        self.manager.remove_monitor(mon_id)

    def test_scan(self):
        devs = self.manager.scanned_devices
        assert len(devs) == 0

        self.adapter.advertise()

        #Let the ioloop process the advertisements
        try:
            self.wait(timeout=0.1)
        except:
            pass

        devs = self.manager.scanned_devices
        assert len(devs) == 1
        assert 1 in devs

    @tornado.testing.gen_test
    def test_connect(self):
        """Make sure we can directly to a device by uuid
        """

        self.adapter.advertise()
        
        yield tornado.gen.sleep(0.1)

        print self.manager.scanned_devices

        res = yield self.manager.connect(1)
        print res

        assert res['success'] is True

    @tornado.testing.gen_test
    def test_reports(self):
        self.adapter.advertise()
        yield tornado.gen.sleep(0.1)

        res = yield self.manager.connect(1)
        conn_id = res['connection_id']

        yield self.manager.open_interface(conn_id, 'streaming')
        yield tornado.gen.sleep(0.1)

        assert len(self.reports) == 1
        print self.reports[0]
