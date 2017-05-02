import pytest
from iotile_transport_awsiot.mqtt_client import OrderedAWSIOTClient


def test_gateway(gateway, local_broker, args):
    """Make sure we can connect to the gateway by sending packets over the mqtt message broker."""

    client = OrderedAWSIOTClient(args)
    client.connect('hello')
    local_broker.expect(2)
    client.publish('devices/d--0000-0000-0000-0002/control/probe', {'type': 'command', 'operation': 'probe', 'client': 'hello'})
    local_broker.wait()


def test_probe(gateway, hw_man, local_broker):
    """Make sure we can probe for devices."""

    local_broker.expect(3)
    results = hw_man.scan(wait=0.1)

    assert len(results) == 1
    assert results[0]['uuid'] == 1
    assert results[0]['connection_string'] == 'd--0000-0000-0000-0001'
