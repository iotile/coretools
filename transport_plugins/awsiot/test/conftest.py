from collections import namedtuple
import pytest
import AWSIoTPythonSDK.MQTTLib

Message = namedtuple('Message', ['topic', 'payload'])


class LocalBroker(object):
    """A very simple in memory MQTT broker
    """

    listeners = {}
    messages = {}

    def __init__(self, client_id, useWebsocket=False):
        self.client = client_id
        self.websocket = useWebsocket

    def configureEndpoint(self, endpoint, port):
        return

    def configureCredentials(self, root, key, cert):
        return

    def configureOfflinePublishQueueing(self, queuing):
        return

    def connect(self):
        return

    def disconnect(self):
        return

    def publish(self, topic, message, qos):
        if topic not in self.messages:
            self.messages[topic] = []

        self.messages[topic].append(message)

        if topic not in self.listeners:
            return

        msg_obj = Message(topic, message)

        for _, callback in self.listeners[topic].iteritems():
            callback(self.client, None, msg_obj)

    def subscribe(self, topic, qos, callback):
        if topic not in self.listeners:
            self.listeners[topic] = {}

        self.listeners[topic][self.client] = callback


@pytest.fixture(scope='function')
def local_broker(monkeypatch):
    """Monkeypatch AWSIoTPythonSDK to pubsub locally
    """

    monkeypatch.setattr(AWSIoTPythonSDK.MQTTLib, 'AWSIoTMQTTClient', LocalBroker)
    LocalBroker.listeners = {}
    LocalBroker.messages = {}

    yield LocalBroker('test_id')

    LocalBroker.listeners = {}
    LocalBroker.messages = {}

@pytest.fixture
def args():
    args = {}
    args['certificate'] = ''
    args['private_key'] = ''
    args['root_certificate'] = ''
    args['endpoint'] = ''

    return args
