import time
from iotile.mock.mock_iotile import MockIOTileDevice
from iotile.mock.mock_adapter import MockDeviceAdapter
from iotile.core.hw.hwmanager import HardwareManager
from iotilegateway.device import DeviceManager
from iotilegateway.wshandler import WebSocketHandler
from iotile.core.hw.reports.individual_format import IndividualReadingReport
from iotile.core.hw.reports.report import IOTileReading
import tornado.gen
import tornado.testing
from util_async import AsyncWebSocketsTestCase


class TestWebSocketInterface(AsyncWebSocketsTestCase):
    def _initialize(self):
        self.dev = MockIOTileDevice(1, 'TestCN')
        self.dev.reports = [IndividualReadingReport.FromReadings(100, [IOTileReading(0, 1, 2)])]
        self.adapter = MockDeviceAdapter()
        self.adapter.add_device('test', self.dev)

        self.manager = DeviceManager(self.io_loop)
        self.manager.add_adapter(self.adapter)
        self.hw = None

    def _deinitialize(self):
        pass

    def _get_app(self):
        app = tornado.web.Application([
            (r'/iotile/v1', WebSocketHandler, {'manager': self.manager})
        ])

        return app

    @tornado.gen.coroutine
    def ensure_advertised(self):
        self.adapter.advertise()

        yield tornado.gen.sleep(0.1)
        devs = self.manager.scanned_devices
        assert len(devs) == 1
        assert 1 in devs

    @tornado.concurrent.run_on_executor
    def get_hwmanager(self):
        hw = HardwareManager(port=self.get_iotile_port())
        return hw

    @tornado.concurrent.run_on_executor
    def connect(self, uuid):
        self.hw.connect(uuid)

    @tornado.concurrent.run_on_executor
    def enable_streaming(self):
        self.hw.enable_streaming()

    @tornado.testing.gen_test
    def test_basic_connection(self):
        yield self.ensure_advertised()

        self.hw = yield self.get_hwmanager()
        yield self.connect(1)

    @tornado.testing.gen_test
    def test_reports(self):
        yield self.ensure_advertised()

        self.hw = yield self.get_hwmanager()
        yield self.connect(1)

        assert self.hw.count_reports() == 0
        yield self.enable_streaming()

        #Give time for report to be processed
        time.sleep(0.1)

        assert self.hw.count_reports() == 1
