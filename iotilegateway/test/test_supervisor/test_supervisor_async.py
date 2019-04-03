"""Unit tests for async async_supervisor server and client."""

import pytest
from iotile.core.exceptions import ArgumentError
import iotilegateway.supervisor.states as states


def test_list_services(loop, async_supervisor):
    """Make sure we can pull a service list from the async_supervisor."""

    _visor, client = async_supervisor

    services = loop.run_coroutine(client.list_services())

    assert len(services) == 2
    assert 'service1' in services
    assert 'service2' in services


def test_query_service(loop, async_supervisor):
    """Make sure we can query a service's status."""

    _visor, client = async_supervisor

    status = loop.run_coroutine(client.service_status('service2'))

    assert status['numeric_status'] == states.UNKNOWN

    with pytest.raises(ArgumentError):
        loop.run_coroutine(client.service_status('service3'))


def test_register_service(loop, async_supervisor):
    """Make sure we can register a new service."""

    _visor, client = async_supervisor
    loop.run_coroutine(client.register_service('service3', 'A nice service'))

    # Make sure the notification made it to our local services
    assert (2, 'service3') in client.local_services()

    servs = loop.run_coroutine(client.list_services())
    assert len(servs) == 3
    assert 'service3' in servs


def test_service_syncing(loop, async_supervisor):
    """Make sure we get updates on service changes."""

    _visor, client = async_supervisor
    loop.run_coroutine(client.register_service('service3', 'A nice service'))

    # Make sure the update got synced
    loop.run_coroutine(client.service_info('service3'))

    assert len(client.services) == 3
    assert 'service3' in client.services

    serv = client.services['service3']
    assert serv.long_name == 'A nice service'
    assert serv.preregistered is False
    assert serv.id == 2

    # Update the state of a service and make sure it gets synced
    loop.run_coroutine(client.update_state('service3', states.RUNNING))
    loop.run_coroutine(client.service_info('service3'))

    assert client.services['service3'].state == states.RUNNING
    assert client.services['service3'].string_state == states.KNOWN_STATES[states.RUNNING]


def test_service_info(loop, async_supervisor):
    """Make sure we can register a new service and get info."""

    _visor, client = async_supervisor
    status = loop.run_coroutine(client.service_info('service2'))
    assert status['long_name'] == 'Service 2'
    assert status['preregistered'] is True

    loop.run_coroutine(client.register_service('service3', 'A nice service'))
    status = loop.run_coroutine(client.service_info('service3'))
    assert status['long_name'] == 'A nice service'
    assert status['preregistered'] is False


def test_service_heartbeat(loop, async_supervisor):
    """Make sure we get updates on service heartbeats."""

    _visor, client = async_supervisor

    loop.run_coroutine(client.service_info('service1'))

    assert client.services['service1'].num_heartbeats == 0

    loop.run_coroutine(client.send_heartbeat('service1'))
    loop.run_coroutine(client.service_info('service1'))
    assert client.services['service1'].num_heartbeats == 1

    loop.run_coroutine(client.send_heartbeat('service1'))
    loop.run_coroutine(client.service_info('service1'))
    assert client.services['service1'].num_heartbeats == 2


def test_query_messages(loop, async_supervisor):
    """Make sure we can set, sync and query messages from the async_supervisor."""

    _visor, client = async_supervisor
    msgs = loop.run_coroutine(client.get_messages('service1'))
    assert len(msgs) == 0

    client.post_error('service1', 'test 1')
    client.post_error('service1', 'test 1')
    client.post_error('service1', 'test 2')
    client.post_error('service1', 'test 3')
    client.post_error('service1', 'test 2')

    #loop.run_coroutine(asyncio.sleep(0.5))
    msgs = loop.run_coroutine(client.get_messages('service1'))

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


def test_service_headline(loop, async_supervisor):
    """Make sure we can set, sync and query headlines."""

    _visor, client = async_supervisor

    msg = loop.run_coroutine(client.get_headline('service1'))
    assert msg is None

    client.post_headline('service1', states.ERROR_LEVEL, 'test message')
    msg = loop.run_coroutine(client.get_headline('service1'))

    assert msg.level == states.ERROR_LEVEL
    assert msg.message == 'test message'
    assert msg.count == 1

    local = client.local_service('service1')
    assert local.headline is not None
    assert local.headline.message == 'test message'

    # Make sure we can change the headline
    client.post_headline('service1', states.INFO_LEVEL, 'info message')
    msg = loop.run_coroutine(client.get_headline('service1'))
    assert msg.level == states.INFO_LEVEL
    assert msg.message == 'info message'

    local = client.local_service('service1')
    assert local.headline is not None
    assert local.headline.message == 'info message'
