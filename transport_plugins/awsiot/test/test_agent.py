import pytest
from iotile_transport_awsiot.gateway_agent import AWSIOTGatewayAgent
from iotilegateway.device import DeviceManager
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
