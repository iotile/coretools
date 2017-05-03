from iotile_transport_awsiot.mqtt_client import OrderedAWSIOTClient


def test_basic_functionality(local_broker, args):
    """Make sure we can create an AWSIOTClient
    """

    client = OrderedAWSIOTClient(args)
    client.connect('hello')
    client.publish('test_topic', 'hello')
