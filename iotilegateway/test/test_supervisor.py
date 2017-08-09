"""Unit tests for supervisor server and client."""

import pytest
import logging
from iotilegateway.supervisor import IOTileSupervisor
from iotilegateway.supervisor.status_client import ServiceStatusClient
import iotilegateway.supervisor.states as states
import tornado.gen
import tornado.testing
from util_async import AsyncWebSocketsTestCase
from iotile.core.exceptions import ArgumentError


@pytest.fixture(scope="function")
def supervisor():
    """A running supervisor with two connected status clients."""

    info = {
        'expected_services':
        [
            {
                "short_name": "service1",
                "long_name": "Service 1"
            },

            {
                "short_name": "service2",
                "long_name": "Service 2"
            }
        ],
        'port': 'unused'  # Bind an unused port for testing, the value will appear on visor.port after visor.loaded is set
    }

    visor = IOTileSupervisor(info)

    visor.start()
    signaled = visor.loaded.wait(2.0)
    if not signaled:
        raise ValueError("Could not start supervisor service")

    port = visor.port
    client1 = ServiceStatusClient('ws://127.0.0.1:%d/services' % port)

    yield visor, client1

    client1.stop()
    visor.stop()


def test_list_services(supervisor):
    """Make sure we can pull a service list from the supervisor."""

    _visor, client = supervisor
    servs = client.list_services()

    assert len(servs) == 2
    assert 'service1' in servs
    assert 'service2' in servs


def test_query_service(supervisor):
    """Make sure we can query a service's status."""

    _visor, client = supervisor
    status = client.service_status('service2')

    assert status['numeric_status'] == states.UNKNOWN

    with pytest.raises(ArgumentError):
        client.service_status('service3')


def test_register_service(supervisor):
    """Make sure we can register a new service."""

    _visor, client = supervisor
    client.register_service('service3', 'A nice service')

    servs = client.list_services()
    assert len(servs) == 3
    assert 'service3' in servs


def test_service_syncing(supervisor):
    """Make sure we get updates on service changes."""

    _visor, client = supervisor
    client.register_service('service3', 'A nice service')

    # Make sure the update got synced
    client.service_info('service3')

    assert len(client.services) == 3
    assert 'service3' in client.services

    serv = client.services['service3']
    assert serv.long_name == 'A nice service'
    assert serv.preregistered is False
    assert serv.id == 2

    # Update the state of a service and make sure it gets synced
    client.update_state('service3', states.RUNNING)
    client.service_info('service3')

    assert client.services['service3'].state == states.RUNNING
    assert client.services['service3'].string_state == states.KNOWN_STATES[states.RUNNING]


def test_service_info(supervisor):
    """Make sure we can register a new service."""

    _visor, client = supervisor
    status = client.service_info('service2')
    assert status['long_name'] == 'Service 2'
    assert status['preregistered'] is True

    client.register_service('service3', 'A nice service')
    status = client.service_info('service3')
    assert status['long_name'] == 'A nice service'
    assert status['preregistered'] is False


def test_service_heartbeat(supervisor):
    """Make sure we get updates on service heartbeats."""

    _visor, client = supervisor

    assert client.services['service1'].num_heartbeats == 0

    client.send_heartbeat('service1')
    client.service_info('service1')
    assert client.services['service1'].num_heartbeats == 1

    client.send_heartbeat('service1')
    client.service_info('service1')
    assert client.services['service1'].num_heartbeats == 2


def test_query_messages(supervisor):
    """Make sure we can set, sync and query messages from the supervisor."""

    _visor, client = supervisor

    msgs = client.get_messages('service1')
    assert len(msgs) == 0

    client.post_error('service1', 'test 1')
    client.post_error('service1', 'test 1')
    client.post_error('service1', 'test 2')
    client.post_error('service1', 'test 3')
    client.post_error('service1', 'test 2')

    msgs = client.get_messages('service1')
    assert len(msgs) == 4
    assert msgs[0].count == 2
    assert msgs[0].message == 'test 1'
    assert msgs[1].count == 1
    assert msgs[1].message == 'test 2'
    assert msgs[2].count == 1
    assert msgs[2].message == 'test 3'
    assert msgs[3].count == 1
    assert msgs[3].message == 'test 2'

    # Now make sure the messages got properly synced locally as well
    local = client.local_service('service1')
    msgs = local.messages
    assert len(msgs) == 4
    assert msgs[0].count == 2
    assert msgs[0].message == 'test 1'
    assert msgs[1].count == 1
    assert msgs[1].message == 'test 2'
    assert msgs[2].count == 1
    assert msgs[2].message == 'test 3'
    assert msgs[3].count == 1
    assert msgs[3].message == 'test 2'


def test_service_headline(supervisor):
    """Make sure we can set, sync and query headlines."""

    _visor, client = supervisor

    msg = client.get_headline('service1')
    assert msg is None

    client.post_headline('service1', states.ERROR_LEVEL, 'test message')
    msg = client.get_headline('service1')

    assert msg.level == states.ERROR_LEVEL
    assert msg.message == 'test message'
    assert msg.count == 1

    local = client.local_service('service1')
    assert local.headline is not None
    assert local.headline.message == 'test message'

    # Make sure we can change the headline
    client.post_headline('service1', states.INFO_LEVEL, 'info message')
    msg = client.get_headline('service1')
    assert msg.level == states.INFO_LEVEL
    assert msg.message == 'info message'

    local = client.local_service('service1')
    assert local.headline is not None
    assert local.headline.message == 'info message'
