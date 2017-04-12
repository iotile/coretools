from iotilegateway.supervisor.ws_handler import ServiceWebSocketHandler
from iotilegateway.supervisor.service_manager import ServiceManager
from iotilegateway.supervisor.status_client import ServiceStatusClient
import tornado.gen
import tornado.testing
from util_async import AsyncWebSocketsTestCase


class TestSupervisor(AsyncWebSocketsTestCase):
    def initialize(self):
        services = [{'short_name': 'service1', 'long_name': 'Service 1'}, {'short_name': 'service2', 'long_name': 'Service 2'}]
        self.manager = ServiceManager(services)
        self.client = None

    def deinitialize(self):
        if self.client is not None:
            self.client.close()

    def get_app(self):
        app = tornado.web.Application([
            (r'/services', ServiceWebSocketHandler, {'manager': self.manager})
        ])

        return app

    @tornado.concurrent.run_on_executor
    def get_client(self):
        self.client = ServiceStatusClient(self.get_supervisor_port())
        return self.client

    @tornado.concurrent.run_on_executor
    def list_services(self):
        servs = self.client.pull_service_list()
        return servs

    @tornado.testing.gen_test
    def test_list_services(self):
        """Make sure we can pull a service list from the supervisor
        """

        yield self.get_client()
        servs = yield self.list_services()

        assert len(servs) == 2
        assert 'service1' in servs
        assert 'service2' in servs
