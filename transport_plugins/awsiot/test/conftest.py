from collections import namedtuple
import threading
import pytest
import time
import os
import json
from monotonic import monotonic
import AWSIoTPythonSDK.MQTTLib
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.dev.registry import ComponentRegistry
from iotilegateway.gateway import IOTileGateway
from builtins import range
from future.utils import viewitems

Message = namedtuple('Message', ['topic', 'payload'])


class LocalBroker(object):
    """A very simple in memory MQTT broker
    """

    listeners = {}
    messages = {}
    sequence = 0
    expected = None
    expect_signal = threading.Event()

    def __init__(self, client_id, useWebsocket=False):
        self.client = client_id
        self.websocket = useWebsocket

    @classmethod
    def Reset(cls):
        cls.listeners = {}
        cls.messages = {}
        cls.sequence = 0
        cls.expected = None
        cls.expect_signal.clear()

    def configureEndpoint(self, endpoint, port):
        return

    def configureCredentials(self, root, key=None, cert=None):
        return

    def configureIAMCredentials(self, key, secret, session=None):
        return

    def configureOfflinePublishQueueing(self, queuing):
        return

    def connect(self):
        return

    def disconnect(self):
        return

    def expect(self, count):
        """Expect a number of messages to be received."""

        LocalBroker.expected = LocalBroker.sequence + count
        LocalBroker.expect_signal.clear()

    def wait(self):
        LocalBroker.expect_signal.wait(timeout=2.0)
        LocalBroker.expected = None

    def wait_subscriptions(self, count, timeout=2.0):
        """Wait for a specific number of subscriptions to be made."""

        start = monotonic()
        while (monotonic() - start) <= timeout:
            if len(self.listeners) >= count:
                return

            time.sleep(0.01)

        raise ValueError("Not enough subscriptions were registered in timeout period")

    def find_topic(self, topic):
        """Find a matching topic including wildcards."""

        parts = topic.split('/')

        for topic in self.listeners:
            list_parts = topic.split('/')
            if len(parts) != len(list_parts):
                continue

            matched = True
            for i in range(0, len(parts)):
                if (parts[i] != list_parts[i]) and list_parts[i] != '+':
                    matched = False
                    break

            if matched:
                return topic

        return None

    def publish(self, topic, message, qos):
        if topic not in self.messages:
            self.messages[topic] = []

        seq = LocalBroker.sequence
        LocalBroker.sequence += 1

        self.messages[topic].append((seq, message))

        # Look for a match including wildcards
        matched_topic = self.find_topic(topic)
        if matched_topic in self.listeners:
            msg_obj = Message(topic, message)

            for _, callback in viewitems(self.listeners[matched_topic]):
                callback(self.client, None, msg_obj)

        if LocalBroker.expected is not None and LocalBroker.sequence >= self.expected:
            LocalBroker.expect_signal.set()

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

    LocalBroker.Reset()


@pytest.fixture(scope="function")
def hw_man(gateway, local_broker):
    """Create a HardwareManager that can talk to our gateway over the local broker."""

    reg = ComponentRegistry()
    reg.set_config('awsiot-endpoint', '')
    reg.set_config('awsiot-rootcert', '')
    reg.set_config('awsiot-iamkey', '')
    reg.set_config('awsiot-iamtoken', '')

    hw_dev = HardwareManager(port="awsiot:devices/d--0000-0000-0000-0002")

    yield hw_dev

    hw_dev.close()

@pytest.fixture(scope="function")
def gateway(local_broker, args):
    """Create a gateway serving over a mock AWS IOT MQTT server."""

    with open(os.path.join(os.path.dirname(__file__), 'gateway_config.json'), "r") as infile:
        args = json.load(infile)

    gate = IOTileGateway(args)
    gate.start()

    gate.loaded.wait(timeout=2.0)
    local_broker.wait_subscriptions(3)

    yield gate

    gate.stop()


@pytest.fixture
def args():
    args = {}
    args['certificate'] = ''
    args['private_key'] = ''
    args['root_certificate'] = ''
    args['endpoint'] = ''

    return args
