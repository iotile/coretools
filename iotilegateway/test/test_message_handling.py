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
