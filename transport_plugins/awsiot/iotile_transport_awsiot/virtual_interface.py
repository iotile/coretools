import logging
import time
import json
import traceback
import binascii
from topic_validator import MQTTTopicValidator
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import EnvironmentError, HardwareError, ValidationError
from mqtt_client import OrderedAWSIOTClient

class AWSIOTVirtualInterface(VirtualIOTileInterface):
    """Allow connections to this device over AWS IOT

    Args:
        args (dict): A dictionary of arguments used to configure this interface.
        Currently the only supported arguments are:
            'certificate': A path to an AWS IOT valid certificate file
            'private_key': A path to the private key for the certificate
            'root_certificate': A path to the root certificate for the trust chain,
            'endpoint': A URL for the AWS IOT endpoint to connect to

        All of these arguments are required.
    """

    # Seconds between heartbeats 
    HeartbeatInterval = 1

    def __init__(self, args):
        super(AWSIOTVirtualInterface, self).__init__()

        self.client = None
        self.device = None
        self.slug = None
        self.args = args
        self.topics = None

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self._logger.setLevel(logging.DEBUG)
        self._logger.addHandler(logging.StreamHandler())

        self._last_heartbeat = time.time()

    @classmethod
    def _build_device_slug(cls, device_id):
        idhex = "{:04x}".format(device_id)

        return "d--0000-0000-0000-{}".format(idhex)

    def start(self, device):
        """Start serving access to this VirtualIOTileDevice

        Args:
            device (VirtualIOTileDevice): The device we will be providing access to
        """

        self.device = device

        self.slug = self._build_device_slug(device.iotile_id)
        self.client = OrderedAWSIOTClient(self.args)
        self.client.connect(self.slug)
        self.topics = MQTTTopicValidator('devices/{}'.format(self.slug))
        self._bind_topics()

    def _bind_topics(self):
        """Subscribe to all the topics needed for interaction with this device
        """

        self.client.subscribe(self.topics.rpc_topic, self._on_rpc_message, ordered=False)
        self.client.subscribe(self.topics.connect_topic, self._on_connect_message, ordered=False)
        self.client.subscribe(self.topics.interface_topic, self._on_interface_message, ordered=False)

    def process(self):
        """Periodic nonblocking processes
        """

        now = time.time()
        if now < self._last_heartbeat:
            self._last_heartbeat = now
        elif (now - self._last_heartbeat) > self.HeartbeatInterval:
            self._publish_heartbeat()
            self._last_heartbeat = now

        super(AWSIOTVirtualInterface, self).process()

    def stop(self):
        """Safely shut down this interface
        """

        if self.client is not None:
            self.client.disconnect()

    def _publish_heartbeat(self):
        data = {}

        if self.topics.locked:
            data['locked'] = True
            data['connected_user'] = self.topics.client
        else:
            data['locked'] = False

        data['timestamp'] = str(time.time())

        self.client.publish(self.topics.status_topic, 'heartbeat', data)

    def _publish_error_response(self, exception, custom_type=None):
        """Send an error response to a command

        Args:
            exception (IOTileException): The exception that occurred during processing
        """

        data = {}
        data['reason'] = exception.msg
        data['params'] = exception.params

        if custom_type is None:
            custom_type = 'response'

        self._publish_response(False, data, custom_type)

    def _publish_success_response(self, data=None, custom_type=None):
        """Send a successful acknowledgment to a command

        Args:
            data (dict): optional data to include with the response
            custom_type (string): optional type for this response message, if None
                then 'response' is used.
        """

        if data is None:
            data = {}

        if custom_type is None:
            custom_type = 'response'

        self._publish_response(True, data, custom_type)

    def _publish_response(self, success, data, message_type):
        """Publish the response to a command

        Args:
            success (bool): Whether the command succeeded
            data (dict): The response data to be sent back to the caller
            message_type (string): The message type for this response
        """

        response = {}

        response['success'] = success
        response['payload'] = data

        self.client.publish(self.topics.response_topic, message_type, response)

    def _publish_status(self, message_type, data):
        """Publish a status message

        Args:
            message_type (string): The message type to publish
            data (dict): The status message data to be sent back to the caller
        """

        self.client.publish(self.topics.status_topic, message_type, data)

    def _on_connect_message(self, sequence, topic, message_type, message):
        """Process a connection or disconnection request

        Connection requests must be accompanied with a 32 byte key
        that is used to authenticate further requests.

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        self._logger.debug("received connect message (type=%s): %s", message_type, message)

        try:
            message = self.topics.validate_message(['connect', 'disconnect'], message_type, message)
        except ValidationError, exc:
            self._publish_status('invalid_message', exc.to_dict())
            return

        # NB Connection messages are replied to on the status channel so that 
        # the response channel only contains responses for the currently connected client 
        if message_type == 'connect':
            if self.topics.locked:
                self._publish_status('connection_response', {'active_user': self.topics.client, 'failure_reason': 'User %s connected' % self.topics.client, 'client': message['client'], 'success': False})
            else:
                self.topics.lock(message['key'], message['client'])
                self._audit('ClientConnected')
                self._publish_status('connection_response', {'success': True, 'client': message['client']})
        elif message_type == 'disconnect':
            if not self.topics.locked:
                self._publish_status('invalid_message', {'reason': 'wrong state', 'message': message, 'client': message['client']})
            elif message['key'] != self.topics.key:
                self._publish_status('invalid_message', {'reason': 'invalid key', 'message': message, 'client': message['client']})
            else:
                # This must be called outside of this message handler since it resets topic sequence numbers
                print "received disconnect message: " + str(message)
                self._defer(self._disconnect_client)

    def _disconnect_client(self):
        """Disconnect a currently connected client from this device
        """

        client = self.topics.client

        self.topics.unlock()
        self._audit('ClientDisconnected')
        self.client.reset_sequence(self.topics.connect_topic)
        self.client.reset_sequence(self.topics.interface_topic)
        self.client.reset_sequence(self.topics.rpc_topic)
        self._publish_success_response({"client": client}, custom_type='disconnection_response')

    def _call_rpc(self, message):
        """Call an RPC based on received rpc message

        Args:
            message (dict): The received MQTT message payload containing the details
                of the call
        """

        address = message['address']
        rpc_id = message['rpc_id']
        payload = message['payload']
        status = (1 << 6)
        try:
            response = self.device.call_rpc(address, rpc_id, str(payload))
            if len(response) > 0:
                status |= (1 << 7)
        except (RPCInvalidIDError, RPCNotFoundError):
            status = 2  # FIXME: Insert the correct ID here
            response = ""
        except TileNotFoundError:
            status = 0xFF
            response = ""
        except Exception:
            # Don't allow exceptions in second thread or we will deadlock on
            status = 3
            response = ""

            print("*** EXCEPTION OCCURRED IN RPC ***")
            traceback.print_exc()
            print("*** END EXCEPTION ***")

        self._audit("RPCReceived", rpc_id=rpc_id, address=address, payload=binascii.hexlify(payload), status=status, response=binascii.hexlify(response))


        resp = {
            'status': status,
            'payload': binascii.hexlify(response)
        }

        self._publish_success_response(resp, 'rpc_response')

    def _on_rpc_message(self, sequence, topic, message_type, message):
        """Process a received RPC packet

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        try:
            message = self.topics.validate_message(['rpc'], message_type, message)
        except ValidationError, exc:
            self._publish_status('invalid_message', exc.to_dict())
            return

        self._defer(self._call_rpc, [message])

    def _on_interface_message(self, sequence, topic, message_type, message):
        """Process a request to open an interface

        Not all interfaces have actions associated with opening them though.
        In particular, opening the rpc interface is a noop.  Opening the 
        streaming interface or tracing interface could result in reports or
        tracing data streaming back to the client though.

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        try:
            message = self.topics.validate_message(['open_interface', 'close_interface'], message_type, message)
        except ValidationError, exc:
            self._publish_status('invalid_message', exc.to_dict())
            return

        key = message['key']
        if self.topics.key != key:
            self._publish_status('message with incorrect key', message)
            return

        if message_type == 'open_interface':
            iface = message['interface']

            if iface == 'rpc':
                self.device.open_rpc_interface()
                self._audit('RPCInterfaceOpened')
            elif iface == 'streaming':
                reports = self.device.open_streaming_interface()
                self._audit('StreamingInterfaceOpened')
                self._queue_reports(reports)
            elif iface == 'tracing':
                traces = self.device.open_tracing_interface()
                self._audit('TracingInterfaceOpened')
                self._queue_traces(traces)
            elif iface == 'script':
                self.open_script_interface()

            self._publish_success_response(custom_type='open_interface_response')
        elif message_type == 'close_interface':
            iface = message['interface']

            if iface == 'rpc':
                self.device.close_rpc_interface()
            elif iface == 'streaming':
                self.device.close_streaming_interface()
                self._audit('StreamingInterfaceClosed')
            elif iface == 'tracing':
                self.device.close_tracing_interface()
                self._audit('TracingInterfaceClosed')
            elif iface == 'script':
                self.close_script_interface()

            self._publish_success_response(custom_type='close_interface_response')
