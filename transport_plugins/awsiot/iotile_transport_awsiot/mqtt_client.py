import json
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.exception import operationError
from iotile.core.exceptions import ArgumentError, EnvironmentError, InternalError
from packet_queue import PacketQueue
from topic_sequencer import TopicSequencer

class OrderedAWSIOTClient(object):
    """An MQTT based channel to connect with an IOTile Device

    Args:
        args (dict): A dictionary of arguments for setting up the
            MQTT connection.
    """

    def __init__(self, args):
        cert = args.get('certificate', None)
        key = args.get('private_key', None)
        root = args.get('root_certificate', None)
        endpoint = args.get('endpoint', None)

        if cert is None:
            raise EnvironmentError("Certificate for AWS IOT not passed in certificate key")
        elif key is None:
            raise EnvironmentError("Private key for certificate not passed in private_key key")
        elif root is None:
            raise EnvironmentError ("Root of certificate chain not passed in root_certificate key")
        elif endpoint is None:
            raise EnvironmentError("AWS IOT endpoint not passed in endpoint key")

        self.cert = cert
        self.key = key
        self.root = root
        self.endpoint = endpoint
        self.client = None
        self.sequencer = TopicSequencer()
        self.queues = {}

    def connect(self, client_id):
        """Connect to AWS IOT with the given client_id

        Args:
            client_id (string): The client ID passed to the MQTT message broker
        """

        if self.client is not None:
            raise InternalError("Connect called on an alreaded connected MQTT client")

        self.client = AWSIoTMQTTClient(client_id)

        self.client = AWSIoTMQTTClient(client_id)
        self.client.configureEndpoint(self.endpoint, 8883)
        self.client.configureCredentials(self.root, self.key, self.cert)
        self.client.configureOfflinePublishQueueing(0)

        try:
            self.client.connect()
        except operationError, exc:
            raise InternalError("Could not connect to AWS IOT", message=exc.message)

        self.sequencer.reset()

    def disconnect(self):
        """Disconnect from AWS IOT message broker
        """

        if self.client is None:
            return

        try:
            self.client.disconnect()
        except operationError, exc:
            raise InternalError("Could not disconnect from AWS IOT", message=exc.message)

    def publish(self, topic, message_type, message):
        """Publish a json message to a topic with a type and a sequence number

        The actual message will be published as a JSON object:
        {
            "sequence": <incrementing id>,
            "type": type,
            "message": message
        }

        Args:
            topic (string): The MQTT topic to publish in
            message_type (string): The type of message to publish.  This is a freeform
                string
            message (string): The message to publish
        """

        seq = self.sequencer.next_id(topic)

        packet = {
            'sequence': seq,
            'type': message_type,
            'message': message
        }

        serialized_packet = json.dumps(packet)

        try:
            self.client.publish(topic, serialized_packet, 1)
        except operationError, exc:
            raise InternalError("Could not publish message", topic=topic, message=exc.message)

    def subscribe(self, topic, callback):
        """Subscribe to future messages in the given topic

        The contents of topic should be in the format created by self.publish with a
        sequence number of message type encoded as a json string.

        Args:
            topic (string): The MQTT topic to subscribe to
            callback (callable): The callback to call when a new mesage is received
                The signature of callback should be callback(sequence, topic, type, message)
        """

        self.queues[topic] = PacketQueue(0, callback)

        try:
            self.client.subscribe(topic, 1, self._on_receive)
        except operationError, exc:
            raise InternalError("Could not subscribe to topic", topic=topic, message=exc.message)

    def _on_receive(self, client, userdata, message):
        """Callback called whenever we receive a message on a subscribed topic

        Args:
            client (string): The client id of the client receiving the message
            userdata (string): Any user data set with the underlying MQTT client
            message (object): The mesage with a topic and payload.
        """

        print("On receive")

        topic = message.topic
        encoded = message.payload

        try:
            packet = json.loads(encoded)
        except ValueError:
            print("Could not decode json packet: %s" % encoded)
            return

        # FIXME: Error handling here
        seq = packet['sequence']
        message_type = packet['type']
        message_data = packet['message']

        if topic not in self.queues:
            print("Received message for unknown topic: %s" % topic)
            return

        self.queues[topic].receive(seq, [seq, message_type, message_data])
