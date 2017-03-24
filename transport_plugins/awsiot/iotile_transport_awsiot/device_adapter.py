import os
import binascii
import threading
import time
import logging
import traceback
import Queue
import uuid
from iotile.core.exceptions import IOTileException, ArgumentError, HardwareError
from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.dev.registry import ComponentRegistry
from mqtt_client import OrderedAWSIOTClient
from topic_validator import MQTTTopicValidator
from connection_manager import ConnectionManager

class AWSIOTDeviceAdapter(DeviceAdapter):
    """A device adapter allowing connections to devices over AWS IoT

    Args:
        port (string): A optional port string specifying a topic prefix
            to use if we are trying to connect to a gateway, otherwise,
            we assume that we're connecting directly to a device that
            is attached to AWS IoT.
    """

    def __init__(self, port):
        super(AWSIOTDeviceAdapter, self).__init__()

        self.set_config('default_timeout', 5.0)

        reg = ComponentRegistry()
        endpoint = reg.get_config('awsiot-endpoint')
        rootcert = reg.get_config('awsiot-rootcert')
        iamuser = reg.get_config('awsiot-iamkey')
        iamsecret = reg.get_config('awsiot-iamtoken')

        # If we need to debug things, enable low level mqtt logging
        #logging.getLogger('AWSIoTPythonSDK.core.protocol.mqttCore').addHandler(logging.StreamHandler())
        #logging.getLogger('AWSIoTPythonSDK.core.protocol.mqttCore').setLevel(logging.INFO)

        args = {}
        args['endpoint'] = endpoint
        args['root_certificate'] = rootcert
        args['use_websockets'] = True
        args['iam_key'] = iamuser
        args['iam_secret'] = iamsecret

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self._logger.setLevel(logging.INFO)
        self._logger.addHandler(logging.StreamHandler())

        # Port should be a topic prefix that allows us to connect
        # only to subset of IOTile devices managed by a gateway
        # rather than to directly accessible iotile devices.
        if port is None:
            port = ""

        if len(port) > 0 and port[-1] != '/':
            port = port + '/'

        self.client = OrderedAWSIOTClient(args)
        self.name = str(uuid.uuid4())
        self.client.connect(self.name)
        self.prefix = port

        self.conns = ConnectionManager(self.id)
        self.conns.start()

        self.client.subscribe(self.prefix + 'devices/+/data/advertisement', self._on_advertisement, ordered=False)

        self._deferred = Queue.Queue()

    def connect_async(self, connection_id, connection_string, callback):
        """Connect to a device by its connection_string

        This function looks for the device on AWS IOT using the preconfigured
        topic prefix and looking for:
        <prefix>/devices/connection_string

        It then attempts to lock that device for exclusive access and
        returns a callback if successful.

        Args:
            connection_id (int): A unique integer set by the caller for referring to this connection
                once created
            connection_string (string): A device id of the form d--XXXX-YYYY-ZZZZ-WWWW
            callback (callable): A callback function called when the connection has succeeded or
                failed
        """

        topics = MQTTTopicValidator(self.prefix + 'devices/{}'.format(connection_string))
        key = self._generate_key()
        name = self.name

        conn_message = {'action': 'connect', 'key': key, 'client': name}
        context = {'key': key, 'slug': connection_string, 'topics': topics}

        self.conns.begin_connection(connection_id, connection_string, callback, context, self.get_config('default_timeout'))

        self._bind_topics(topics)

        try:
            self.client.publish(topics.connect_topic, 'connect', conn_message)
        except IOTileException:
            self._unbind_topics(topics)
            self.conns.finish_connection(connection_id, False, 'Failed to send connection message')

    def disconnect_async(self, conn_id, callback):
        """Asynchronously disconnect from a device that has previously been connected

        Args:
            conn_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): A function called as callback(conn_id, adapter_id, success, failure_reason)
            when the disconnection finishes.  Disconnection can only either succeed or timeout.
        """

        try:
            context = self.conns.get_context(conn_id)
        except ArgumentError:
            callback(conn_id, self.id, False, "Could not find connection information")
            return

        self.conns.begin_disconnection(conn_id, callback, self.get_config('default_timeout'))

        topics = context['topics']
        disconn_message = {'key': context['key'], 'client': self.name}

        self.client.publish(topics.connect_topic, 'disconnect', disconn_message)

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as" 
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        try:
            context = self.conns.get_context(conn_id)
        except ArgumentError:
            callback(conn_id, self.id, False, "Could not find connection information", 0xFF, bytearray())
            return

        self.conns.begin_operation(conn_id, 'rpc', callback, timeout)

        topics = context['topics']

        encoded_payload = binascii.hexlify(payload)

        rpc_message = {'key': context['key'], 'client': self.name, 'address': address,
                       'rpc_id': rpc_id, 'payload': encoded_payload, 'timeout': timeout}

        self.client.publish(topics.rpc_topic, 'rpc', rpc_message)

    def _open_rpc_interface(self, conn_id, callback):
        """Enable RPC interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.conns.get_context(conn_id)
        except ArgumentError:
            callback(conn_id, self.id, False, "Could not find connection information")
            return

        self.conns.begin_operation(conn_id, 'open_interface', callback, self.get_config('default_timeout'))

        topics = context['topics']

        open_iface_message = {'key': context['key'], 'client': self.name, 'interface': 'rpc'}

        self.client.publish(topics.interface_topic, 'open_interface', open_iface_message)

    def stop_sync(self):
        """Synchronously stop this adapter
        """

        conn_ids = self.conns.get_connections()

        # If we have any open connections, try to close them here before shutting down
        for conn in conn_ids:
            try:
                self.disconnect_sync(conn)
            except HardwareError:
                pass

        self.client.disconnect()
        self.conns.stop()

    def periodic_callback(self):
        """Periodically help maintain adapter internal state
        """

        while True:
            try:
                action = self._deferred.get(False)
                action()
            except Queue.Empty:
                break
            except Exception:
                print("***Exception in periodic callback***")
                traceback.print_exc() 
                print("************************************")

    def _bind_topics(self, topics):
        """Subscribe to all the topics we need to communication with this device

        Args:
            topics (MQTTTopicValidator): The topic validator for this device that
                we are connecting to.
        """

        # FIXME: Allow for these subscriptions to fail and clean up the previous ones
        # so that this function is atomic

        self.client.subscribe(topics.status_topic, self._on_status_message)
        self.client.subscribe(topics.response_topic, self._on_response_message)

    def _unbind_topics(self, topics):
        """Unsubscribe to all of the topics we needed for communication with device

        Args:
            topics (MQTTTopicValidator): The topic validator for this device that
                we have connected to.
        """

        self.client.unsubscribe(topics.status_topic)
        self.client.unsubscribe(topics.response_topic)

    def _generate_key(self):
        """Generate a random 32 byte key and encode it in hex

        Returns:
            string: Cryptographically random 64 character string
        """

        key = os.urandom(32)
        return binascii.hexlify(key)

    def _find_connection(self, topic):
        """Attempt to find a connection id corresponding with a topic

        The device is found by assuming the topic ends in <slug>/[control|data]/channel

        Args:
            topic (string): The topic we received a message on

        Returns:
            int: The internal connect id (device slug) associated with this topic
        """

        parts = topic.split('/')
        if len(parts) < 3:
            return None

        slug = parts[-3]
        return slug

    def _on_advertisement(self, sequence, topic, message_type, message):
        try:
            # FIXME: We need a global topic validator to validate these messages
            #message = self.topics.validate_message(['advertisement'], message_type, message)

            self._trigger_callback('on_scan', self.id, message, 60.) # FIXME: Get the timeout from somewhere
        except IOTileException, exc:
            pass

    def _on_status_message(self, sequence, topic, message_type, message):
        """Process a status message received

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        self._logger.debug("Received message on (topic=%s): %s" % (topic, str(message)))

        try:
            conn_key = self._find_connection(topic)
            context = self.conns.get_context(conn_key)
        except ArgumentError:
            print("Dropping message that does not correspond with a known connection")
            return

        topics = context['topics']

        try:
            message = topics.validate_message(['heartbeat', 'disconnection_response', 'connection_response'], message_type, message)

            # If a status message is directed at a specific client that's not us, ignore it
            if 'client' in message and self.name != message['client']:
                return

            # We respond to connection responses only when we are trying to connect
            if message_type == 'connection_response':
                success = message['success']
                if success:
                    self.conns.finish_connection(conn_key, True, None)
                else:
                    self.conns.finish_connection(conn_key, False, message['failure_reason'])
            elif message_type == 'disconnection_response':
                success = message['success']
                if success:
                    # If we disconnect from a device, queue a task to unbind from its topics
                    # We cannot do it here since we would block the paho event loop
                    self._deferred.put(lambda: self._unbind_topics(topics))
                    self.conns.finish_disconnection(conn_key, True, None)
                else:
                    self.conns.finish_disconnection(conn_key, False, message['failure_reason'])
        except IOTileException, exc:
            # Eat all exceptions here because this is a callback in another
            # thread
            print(str(exc))

    def _on_response_message(self, sequence, topic, message_type, message):
        """Process a response message received

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        try:
            conn_key = self._find_connection(topic)
            context = self.conns.get_context(conn_key)
        except ArgumentError:
            print("Dropping message that does not correspond with a known connection")
            return

        topics = context['topics']

        try:
            message = topics.validate_message(['open_interface_response', 'rpc_response'], message_type, message)

            if message_type == 'open_interface_response':
                success = message['success']
                payload = message['payload']
                if success:
                    self.conns.finish_operation(conn_key, True, None)
                else:
                    self.conns.finish_operation(conn_key, False, payload['reason'])
            elif message_type == 'rpc_response':
                success = message['success']
                payload = message['payload']

                if success:
                    status = payload['status']
                    rpc_payload = payload['payload']
                    self.conns.finish_operation(conn_key, True, None, status, rpc_payload)
                else:
                    self.conns.finish_operation(conn_key, False, payload['reason'], None, None)
        except IOTileException, exc:
            # Eat all exceptions here because this is a callback in another
            # thread
            print(str(exc))
