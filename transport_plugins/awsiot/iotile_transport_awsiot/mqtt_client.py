import json
import logging
import AWSIoTPythonSDK.MQTTLib
import re
from AWSIoTPythonSDK.exception.operationError import operationError
from iotile.core.exceptions import ArgumentError, ExternalError, InternalError
from iotile.core.dev.registry import ComponentRegistry
from .packet_queue import PacketQueue
from .topic_sequencer import TopicSequencer


class OrderedAWSIOTClient:
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
        iamkey = args.get('iam_key', None)
        iamsecret = args.get('iam_secret', None)
        iamsession = args.get('iam_session', None)
        use_websockets = args.get('use_websockets', False)

        try:
            if not use_websockets:
                if cert is None:
                    raise ExternalError("Certificate for AWS IOT not passed in certificate key")
                elif key is None:
                    raise ExternalError("Private key for certificate not passed in private_key key")
            else:
                if iamkey is None or iamsecret is None:
                    raise ExternalError("IAM Credentials need to be provided for websockets auth")
        except ExternalError:
            # If the correct information is not passed in, try and see if we get it from our environment
            # try to pull in root certs, endpoint name and iam or cognito session information
            reg = ComponentRegistry()

            if endpoint is None:
                endpoint = reg.get_config('awsiot-endpoint', default=None)

            if root is None:
                root = reg.get_config('awsiot-rootcert', default=None)

            iamkey = reg.get_config('awsiot-iamkey', default=None)
            iamsecret = reg.get_config('awsiot-iamtoken', default=None)
            iamsession = reg.get_config('awsiot-session', default=None)

            if iamkey is None or iamsecret is None:
                raise

            use_websockets = True

        if root is None:
            raise ExternalError("Root of certificate chain not passed in root_certificate key (and not in registry)")
        elif endpoint is None:
            raise ExternalError("AWS IOT endpoint not passed in endpoint key (and not in registry)")

        self.websockets = use_websockets
        self.iam_key = iamkey
        self.iam_secret = iamsecret
        self.iam_session = iamsession
        self.cert = cert
        self.key = key
        self.root = root
        self.endpoint = endpoint
        self.client = None
        self.sequencer = TopicSequencer()
        self.queues = {}
        self.wildcard_queues = []
        self._logger = logging.getLogger(__name__)

    def connect(self, client_id):
        """Connect to AWS IOT with the given client_id

        Args:
            client_id (string): The client ID passed to the MQTT message broker
        """

        if self.client is not None:
            raise InternalError("Connect called on an alreaded connected MQTT client")

        client = AWSIoTPythonSDK.MQTTLib.AWSIoTMQTTClient(client_id, useWebsocket=self.websockets)

        if self.websockets:
            client.configureEndpoint(self.endpoint, 443)
            client.configureCredentials(self.root)

            if self.iam_session is None:
                client.configureIAMCredentials(self.iam_key, self.iam_secret)
            else:
                client.configureIAMCredentials(self.iam_key, self.iam_secret, self.iam_session)
        else:
            client.configureEndpoint(self.endpoint, 8883)
            client.configureCredentials(self.root, self.key, self.cert)

        client.configureOfflinePublishQueueing(0)

        try:
            client.connect()
            self.client = client
        except operationError as exc:
            raise InternalError("Could not connect to AWS IOT", message=exc.message)

        self.sequencer.reset()

    def disconnect(self):
        """Disconnect from AWS IOT message broker
        """

        if self.client is None:
            return

        try:
            self.client.disconnect()
        except operationError as exc:
            raise InternalError("Could not disconnect from AWS IOT", message=exc.message)

    def publish(self, topic, message):
        """Publish a json message to a topic with a type and a sequence number

        The actual message will be published as a JSON object:
        {
            "sequence": <incrementing id>,
            "message": message
        }

        Args:
            topic (string): The MQTT topic to publish in
            message (string, dict): The message to publish
        """

        seq = self.sequencer.next_id(topic)

        packet = {
            'sequence': seq,
            'message': message
        }
        # Need to encode bytes types for json.dumps
        if 'key' in packet['message']:
            packet['message']['key'] = packet['message']['key'].decode('utf8')
        if 'payload' in packet['message']:
            packet['message']['payload'] = packet['message']['payload'].decode('utf8')
        if 'script' in packet['message']:
            packet['message']['script'] = packet['message']['script'].decode('utf8')
        if 'trace' in packet['message']:
            packet['message']['trace'] = packet['message']['trace'].decode('utf8')
        if 'report' in packet['message']:
            packet['message']['report'] = packet['message']['report'].decode('utf8')
        if 'received_time' in packet['message']:
            packet['message']['received_time'] = packet['message']['received_time'].decode('utf8')

        serialized_packet = json.dumps(packet)

        try:
            # Limit how much we log in case the message is very long
            self._logger.debug("Publishing %s on topic %s", serialized_packet[:256], topic)
            self.client.publish(topic, serialized_packet, 1)
        except operationError as exc:
            raise InternalError("Could not publish message", topic=topic, message=exc.message)

    def subscribe(self, topic, callback, ordered=True):
        """Subscribe to future messages in the given topic

        The contents of topic should be in the format created by self.publish with a
        sequence number of message type encoded as a json string.

        Wildcard topics containing + and # are allowed and

        Args:
            topic (string): The MQTT topic to subscribe to
            callback (callable): The callback to call when a new mesage is received
                The signature of callback should be callback(sequence, topic, type, message)
            ordered (bool): Whether messages on this topic have a sequence number that must
                be checked and queued to ensure that packets are received in order
        """

        if '+' in topic or '#' in topic:
            regex = re.compile(topic.replace('+', '[^/]+').replace('#', '.*'))
            self.wildcard_queues.append((topic, regex, callback, ordered))
        else:
            self.queues[topic] = PacketQueue(0, callback, ordered)

        try:
            self.client.subscribe(topic, 1, self._on_receive)
        except operationError as exc:
            raise InternalError("Could not subscribe to topic", topic=topic, message=exc.message)

    def reset_sequence(self, topic):
        """Reset the expected sequence number for a topic

        If the topic is unknown, this does nothing.  This behaviour is
        useful when you have wildcard topics that only create queues
        once they receive the first message matching the topic.

        Args:
            topic (string): The topic to reset the packet queue on
        """

        if topic in self.queues:
            self.queues[topic].reset()

    def unsubscribe(self, topic):
        """Unsubscribe from messages on a given topic

        Args:
            topic (string): The MQTT topic to unsubscribe from
        """

        del self.queues[topic]

        try:
            self.client.unsubscribe(topic)
        except operationError as exc:
            raise InternalError("Could not unsubscribe from topic", topic=topic, message=exc.message)

    def _on_receive(self, client, userdata, message):
        """Callback called whenever we receive a message on a subscribed topic

        Args:
            client (string): The client id of the client receiving the message
            userdata (string): Any user data set with the underlying MQTT client
            message (object): The mesage with a topic and payload.
        """

        topic = message.topic
        encoded = message.payload

        try:
            packet = json.loads(encoded)
        except ValueError:
            self._logger.warn("Could not decode json packet: %s", encoded)
            return

        try:
            seq = packet['sequence']
            message_data = packet['message']
        except KeyError:
            self._logger.warn("Message received did not have required sequence and message keys: %s", packet)
            return

        # If we received a packet that does not fit into a queue, check our wildcard
        # queues
        if topic not in self.queues:
            found = False
            for _, regex, callback, ordered in self.wildcard_queues:
                if regex.match(topic):
                    self.queues[topic] = PacketQueue(0, callback, ordered)
                    found = True
                    break

            if not found:
                self._logger.warn("Received message for unknown topic: %s", topic)
                return

        self.queues[topic].receive(seq, [seq, topic, message_data])
