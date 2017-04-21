"""Unit tests for service message caching."""

import pytest
import iotilegateway.supervisor.states as states
from iotile.core.exceptions import ArgumentError


@pytest.fixture
def service():
    serv = states.ServiceState('test', 'A test service', False, int_id=5, max_messages=10)
    return serv


def test_creating_service():
    """Make sure we can create a service."""

    serv = states.ServiceState('test', 'A test service', False, int_id=5, max_messages=10)

    assert serv.short_name == 'test'
    assert serv.long_name == 'A test service'
    assert serv.preregistered is False
    assert serv.id == 5
    assert serv.state == states.UNKNOWN


def test_posting_messages(service):
    """Make sure we can post messages and read them back."""

    service.post_message(states.INFO_LEVEL, 'test message')
    service.post_message(states.WARNING_LEVEL, 'test 2 message')

    assert len(service.messages) == 2
    assert service.messages[0].level == states.INFO_LEVEL
    assert service.messages[0].message == 'test message'
    assert service.messages[0].count == 1
    assert service.messages[0].id == 0

    assert service.messages[1].level == states.WARNING_LEVEL
    assert service.messages[1].message == 'test 2 message'
    assert service.messages[1].count == 1
    assert service.messages[1].id == 1


def test_duplicate_messages(service):
    """Make sure duplicate messages are deduplicated."""

    service.post_message(states.INFO_LEVEL, 'test message')
    service.post_message(states.INFO_LEVEL, 'test message')

    assert len(service.messages) == 1
    assert service.messages[0].level == states.INFO_LEVEL
    assert service.messages[0].message == 'test message'
    assert service.messages[0].count == 2
    assert service.messages[0].id == 0


def test_message_creation():
    """Make sure messages can be serialized and deserialized."""

    ts = 1000.0
    now = 1010.0

    msg = states.ServiceMessage(states.ERROR_LEVEL, 'test message', 15, ts, now)

    msg_dict = msg.to_dict()
    new_msg = states.ServiceMessage.FromDictionary(msg_dict)

    msg_age = msg_dict['now_time'] - msg_dict['created_time']
    del msg_dict['created_time']
    del msg_dict['now_time']

    new_dict = new_msg.to_dict()
    new_age = new_dict['now_time'] - new_dict['created_time']
    del new_dict['created_time']
    del new_dict['now_time']

    # The message ages should be identical to within a few lsbs of a float but
    # technically we don't really care how precise it is
    assert abs(new_age - msg_age) < 0.1
    assert msg_dict == new_dict
    assert new_msg.level == states.ERROR_LEVEL
    assert new_msg.message == 'test message'
    assert new_msg.id == 15
    assert new_msg.count == 1
