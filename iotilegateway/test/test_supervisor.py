"""Unit tests for supervisor server and client."""

import pytest
from iotilegateway.supervisor.ws_handler import ServiceWebSocketHandler
from iotilegateway.supervisor.service_manager import ServiceManager
from iotilegateway.supervisor.status_client import ServiceStatusClient
import iotilegateway.supervisor.states as states
import tornado.gen
import tornado.testing
from util_async import AsyncWebSocketsTestCase
from iotile.core.exceptions import ArgumentError



class TestSupervisor(AsyncWebSocketsTestCase):
    """Test the supervisor service and websocket synchronizing client."""

    def _initialize(self):
        services = [{'short_name': 'service1', 'long_name': 'Service 1'}, {'short_name': 'service2', 'long_name': 'Service 2'}]
        self.manager = ServiceManager(services)
        self.client = None

    @tornado.concurrent.run_on_executor
    def _preshutdown_deinitialize(self):
        if self.client is not None:
            self.client.stop()

    def _get_app(self):
        app = tornado.web.Application([
            (r'/services', ServiceWebSocketHandler, {'manager': self.manager})
        ])

        return app

    @tornado.concurrent.run_on_executor
    def _get_client(self):
        self.client = ServiceStatusClient(self.get_supervisor_port())
        return self.client

    @tornado.concurrent.run_on_executor
    def _list_services(self):
        servs = self.client.list_services()
        return servs

    @tornado.concurrent.run_on_executor
    def _query_service(self, name):
        status = self.client.service_status(name)
        return status

    @tornado.concurrent.run_on_executor
    def _query_info(self, name):
        status = self.client.service_info(name)
        return status

    @tornado.concurrent.run_on_executor
    def _heartbeat(self, name):
        self.client.send_heartbeat(name)

    @tornado.concurrent.run_on_executor
    def _register_service(self, short_name, long_name):
        status = self.client.register_service(short_name, long_name)
        return status

    @tornado.concurrent.run_on_executor
    def _update_state(self, short_name, state):
        self.client.update_state(short_name, state)

    @tornado.testing.gen_test
    def test_list_services(self):
        """Make sure we can pull a service list from the supervisor."""

        yield self._get_client()
        servs = yield self._list_services()

        assert len(servs) == 2
        assert 'service1' in servs
        assert 'service2' in servs

    @tornado.testing.gen_test
    def test_query_status(self):
        """Make sure we can query a service's status."""

        yield self._get_client()
        status = yield self._query_service('service2')

        assert status['numeric_status'] == states.UNKNOWN

        with pytest.raises(ArgumentError):
            yield self._query_service('service3')

    @tornado.testing.gen_test
    def test_register_service(self):
        """Make sure we can register a new service."""

        yield self._get_client()
        yield self._register_service('service3', 'A nice service')

        servs = yield self._list_services()
        assert len(servs) == 3
        assert 'service3' in servs

    @tornado.testing.gen_test
    def test_query_info(self):
        """Make sure we can register a new service."""

        yield self._get_client()
        status = yield self._query_info('service2')
        assert status['long_name'] == 'Service 2'
        assert status['preregistered'] is True

        yield self._register_service('service3', 'A nice service')
        status = yield self._query_info('service3')
        assert status['long_name'] == 'A nice service'
        assert status['preregistered'] is False

    @tornado.testing.gen_test
    def test_service_syncing(self):
        """Make sure we get updates on service changes."""

        yield self._get_client()
        yield self._register_service('service3', 'A nice service')

        # Make sure the update got synced
        yield self._query_info('service3')

        assert len(self.client.services) == 3
        assert 'service3' in self.client.services

        serv = self.client.services['service3']
        assert serv.long_name == 'A nice service'
        assert serv.preregistered is False
        assert serv.id == 2

        # Update the state of a service and make sure it gets synced
        yield self._update_state('service3', states.RUNNING)
        yield self._query_info('service3')

        assert self.client.services['service3'].state == states.RUNNING
        assert self.client.services['service3'].string_state == states.KNOWN_STATES[states.RUNNING]

    @tornado.testing.gen_test
    def test_service_heartbeat(self):
        """Make sure we get updates on service heartbeats."""

        yield self._get_client()

        assert self.client.services['service1'].num_heartbeats == 0

        yield self._heartbeat('service1')
        yield self._query_info('service1')
        assert self.client.services['service1'].num_heartbeats == 1

        yield self._heartbeat('service1')
        yield self._query_info('service1')
        assert self.client.services['service1'].num_heartbeats == 2
