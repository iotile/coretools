"""Unit tests for async supervisor server and client."""

import pytest
import logging
from iotilegateway.supervisor import IOTileSupervisor
from iotilegateway.supervisor.status_client import AsyncServiceStatusClient
import iotilegateway.supervisor.states as states
import tornado.gen
import tornado.testing
from util_async import AsyncWebSocketsTestCase
from iotile.core.exceptions import ArgumentError


import asyncio

from iotile.core.utilities.event_loop import EventLoop


@pytest.fixture(scope="function")
def supervisor():
    """A running supervisor with two connected status clients."""

    print("setting up supervisor")

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
        'port': 'unused'  # Bind an unused port for testing, the value
                          # will appear on visor.port after visor.loaded is set
    }

    visor = IOTileSupervisor(info)

    visor.start()
    signaled = visor.loaded.wait(2.0)
    if not signaled:
        raise ValueError("Could not start supervisor service")

    port = visor.port
    client1 = AsyncServiceStatusClient('ws://127.0.0.1:%d/services' % port)

    yield visor, client1

    #client1.stop()
    visor.stop()


def test_list_services(supervisor):
    """Make sure we can pull a service list from the supervisor."""

    print("test list services")
    _visor, client = supervisor

    servs = asyncio.run_coroutine_threadsafe(client.list_services(), loop=EventLoop.get_loop()).result()
    print("THE SERVES are", servs)

    assert len(servs) == 2
    assert 'service1' in servs
    assert 'service2' in servs


def test_query_service(supervisor):
    """Make sure we can query a service's status."""

    _visor, client = supervisor

    status = asyncio.run_coroutine_threadsafe(client.service_status('service2'), loop=EventLoop.get_loop()).result()

    assert status['numeric_status'] == states.UNKNOWN

    with pytest.raises(ArgumentError):
        asyncio.run_coroutine_threadsafe(client.service_status('service3'), loop=EventLoop.get_loop()).result()


def test_register_service(supervisor):
    """Make sure we can register a new service."""

    _visor, client = supervisor
    asyncio.run_coroutine_threadsafe(client.register_service('service3', 'A nice service'),
                                     loop=EventLoop.get_loop()).result()

    servs = asyncio.run_coroutine_threadsafe(client.list_services(), loop=EventLoop.get_loop()).result()
    assert len(servs) == 3
    assert 'service3' in servs


def test_service_syncing(supervisor):
    """Make sure we get updates on service changes."""

    _visor, client = supervisor
    asyncio.run_coroutine_threadsafe(client.register_service('service3', 'A nice service'),
                                     loop=EventLoop.get_loop()).result()

    # Make sure the update got synced
    asyncio.run_coroutine_threadsafe(client.service_info('service3'), loop=EventLoop.get_loop()).result()

    assert len(client.services) == 3
    assert 'service3' in client.services

    serv = client.services['service3']
    assert serv.long_name == 'A nice service'
    assert serv.preregistered is False
    assert serv.id == 2

    # Update the state of a service and make sure it gets synced
    asyncio.run_coroutine_threadsafe(client.update_state('service3', states.RUNNING),
                                     loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.service_info('service3'), loop=EventLoop.get_loop()).result()

    assert client.services['service3'].state == states.RUNNING
    assert client.services['service3'].string_state == states.KNOWN_STATES[states.RUNNING]


def test_service_info(supervisor):
    """Make sure we can register a new service."""

    _visor, client = supervisor
    status = asyncio.run_coroutine_threadsafe(client.service_info('service2'), loop=EventLoop.get_loop()).result()
    assert status['long_name'] == 'Service 2'
    assert status['preregistered'] is True

    asyncio.run_coroutine_threadsafe(client.register_service('service3', 'A nice service'),
                                     loop=EventLoop.get_loop()).result()
    status = asyncio.run_coroutine_threadsafe(client.service_info('service3'), loop=EventLoop.get_loop()).result()
    assert status['long_name'] == 'A nice service'
    assert status['preregistered'] is False


def test_service_heartbeat(supervisor):
    """Make sure we get updates on service heartbeats."""

    _visor, client = supervisor

    status = asyncio.run_coroutine_threadsafe(client.service_info('service1'), loop=EventLoop.get_loop()).result()

    # Need to wait until the services are populated for the dict to have updated keys
    # Would be better to find an awaitable that actually monitors this dict key
    asyncio.run_coroutine_threadsafe( asyncio.sleep(0.5), loop=EventLoop.get_loop()).result()

    assert client.services['service1'].num_heartbeats == 0

    asyncio.run_coroutine_threadsafe(client.send_heartbeat('service1'), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.service_info('service1'), loop=EventLoop.get_loop()).result()
    assert client.services['service1'].num_heartbeats == 1

    asyncio.run_coroutine_threadsafe(client.send_heartbeat('service1'), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.service_info('service1'), loop=EventLoop.get_loop()).result()
    assert client.services['service1'].num_heartbeats == 2


def test_query_messages(supervisor):
    """Make sure we can set, sync and query messages from the supervisor."""

    _visor, client = supervisor
    msgs = asyncio.run_coroutine_threadsafe(client.get_messages('service1'), loop=EventLoop.get_loop()).result()
    assert len(msgs) == 0

    asyncio.run_coroutine_threadsafe(asyncio.sleep(0.5), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.post_error('service1', 'test 1'), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.post_error('service1', 'test 1'), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.post_error('service1', 'test 2'), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.post_error('service1', 'test 3'), loop=EventLoop.get_loop()).result()
    asyncio.run_coroutine_threadsafe(client.post_error('service1', 'test 2'), loop=EventLoop.get_loop()).result()

    asyncio.run_coroutine_threadsafe(asyncio.sleep(0.5), loop=EventLoop.get_loop()).result()
    msgs = asyncio.run_coroutine_threadsafe(client.get_messages('service1'), loop=EventLoop.get_loop()).result()

    for msg in msgs:
        print(msg.count, ": ", msg.message)
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
    asyncio.run_coroutine_threadsafe(asyncio.sleep(0.5), loop=EventLoop.get_loop()).result()
    local = asyncio.run_coroutine_threadsafe(client.local_service('service1'), loop=EventLoop.get_loop()).result()
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

    msg = asyncio.run_coroutine_threadsafe(client.get_headline('service1'), loop=EventLoop.get_loop()).result()
    assert msg is None

    asyncio.run_coroutine_threadsafe(client.post_headline('service1', states.ERROR_LEVEL, 'test message'),
                                     loop=EventLoop.get_loop()).result()
    msg = asyncio.run_coroutine_threadsafe(client.get_headline('service1'), loop=EventLoop.get_loop()).result()

    assert msg.level == states.ERROR_LEVEL
    assert msg.message == 'test message'
    assert msg.count == 1

    local = asyncio.run_coroutine_threadsafe(client.local_service('service1'), loop=EventLoop.get_loop()).result()
    assert local.headline is not None
    assert local.headline.message == 'test message'

    # Make sure we can change the headline
    asyncio.run_coroutine_threadsafe(client.post_headline('service1', states.INFO_LEVEL, 'info message'),
                                     loop=EventLoop.get_loop()).result()
    msg = asyncio.run_coroutine_threadsafe(client.get_headline('service1'), loop=EventLoop.get_loop()).result()
    assert msg.level == states.INFO_LEVEL
    assert msg.message == 'info message'

    local = asyncio.run_coroutine_threadsafe(client.local_service('service1'), loop=EventLoop.get_loop()).result()
    assert local.headline is not None
    assert local.headline.message == 'info message'
