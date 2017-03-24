import pytest
import pkg_resources
import json
from iotile_transport_awsiot.virtual_interface import AWSIOTVirtualInterface
from iotile_transport_awsiot.mqtt_client import OrderedAWSIOTClient
from iotile_transport_awsiot.topic_validator import MQTTTopicValidator

@pytest.fixture(scope='function')
def client(local_broker, args):
    """A connected client that can send messages to the broker
    """

    client = OrderedAWSIOTClient(args)
    client.connect('test-client')

    yield client

    client.disconnect()

@pytest.fixture(scope='function')
def simple(args, local_broker):
    """Create a virtual interface serving a simple device locally
    """

    iface = AWSIOTVirtualInterface(args)

    dev = None
    for entry in pkg_resources.iter_entry_points('iotile.virtual_device', name='simple'):
        dev = entry.load()
        break

    if dev is None:
        raise ValueError('Could not find simple virtual device in fixture, make sure iotile-test is installed')

    device = dev({'iotile_id': 1})
    iface.start(device)

    yield iface

    iface.stop()

@pytest.fixture
def topics():
    prefix = 'devices/d--0000-0000-0000-0001'
    yield MQTTTopicValidator(prefix)

def expect_success(message, custom_type='response'):

    parsed = json.loads(message)
    payload = parsed['message']

    assert parsed['type'] == custom_type
    assert payload['success'] is True

def expect_failure(message, custom_type='response'):
    parsed = json.loads(message)
    payload = parsed['message']

    assert parsed['type'] == custom_type
    assert payload['success'] is False

def test_connecting(topics, local_broker, client, simple):
    """Test to make sure we can connect to a device
    """

    test_key = 'a'*64
    test_client = 'test-client'

    assert simple.topics.locked is False
    client.publish(topics.connect_topic, 'connect', {'key': test_key, 'client': test_client})

    assert len(local_broker.messages[topics.status_topic]) == 1
    assert simple.topics.locked
    assert simple.topics.key == test_key
    assert simple.topics.client == test_client

    parsed = json.loads(local_broker.messages[topics.status_topic][-1])
    assert parsed['type'] == 'connection_response'
    assert parsed['message']['success'] is True

def test_double_connecting(topics, local_broker, client, simple):
    """Test to make sure multiple connections are disallowed
    """

    test_key = 'a'*64
    test_client = 'test-client'
    test_key2 = 'b'*64
    test_client2 = 'test-client-2'

    assert simple.topics.locked is False
    client.publish(topics.connect_topic, 'connect', {'key': test_key, 'client': test_client})
    client.publish(topics.connect_topic, 'connect', {'key': test_key, 'client': test_client})

    assert len(local_broker.messages[topics.status_topic]) == 2

    # Make sure the first client remains connected
    assert simple.topics.locked
    assert simple.topics.key == test_key
    assert simple.topics.client == test_client

    # Make sure conn 1 succeeded
    parsed = json.loads(local_broker.messages[topics.status_topic][-2])
    assert parsed['type'] == 'connection_response'
    assert parsed['message']['success'] is True

    # Make sure conn 2 failed
    parsed = json.loads(local_broker.messages[topics.status_topic][-1])
    assert parsed['type'] == 'connection_response'
    assert parsed['message']['success'] is False
    assert parsed['message']['active_user'] == test_client

def test_disconnecting(topics, local_broker, client, simple):
    """Test to make sure we can disconnect from a device
    """

    test_key = 'a'*64
    test_client = 'test-client'

    assert simple.topics.locked is False
    client.publish(topics.connect_topic, 'connect', {'key': test_key, 'client': test_client})
    client.publish(topics.connect_topic, 'disconnect', {'key': test_key, 'client': test_client})

    simple.process()
    assert len(local_broker.messages[topics.response_topic]) == 1
    assert simple.topics.locked is False
    assert simple.topics.key is None
    assert simple.topics.client is None

    expect_success(local_broker.messages[topics.response_topic][-1], 'disconnection_response')
