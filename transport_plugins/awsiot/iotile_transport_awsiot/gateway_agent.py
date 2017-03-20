import logging
import tornado.gen
import binascii
import struct
from mqtt_client import OrderedAWSIOTClient
from topic_validator import MQTTTopicValidator
from iotile.core.exceptions import EnvironmentError, ArgumentError, ValidationError

class AWSIOTGatewayAgent(object):
    """An agent for serving access to devices over AWSIOT

    Args:
        manager (DeviceManager): A device manager provided
            by iotile-gateway.
        loop (IOLoop): A tornado IOLoop that this agent
            shold integrate into.
        args (dict): A dictionary of arguments for configuring
            this agent.
    """

    def __init__(self, args, manager, loop):
        self._args = args
        self._manager = manager
        self._advertisement_callback = None
        self._loop = loop
        self.client = None
        self.slug = None
        self.topics = None
        self._connections = {}
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self._logger.setLevel(logging.DEBUG)

        self.prefix = self._args.get('prefix', '')
        if len(self.prefix) > 0 and self.prefix[-1] != '/':
            self.prefix += '/'

        if 'iotile_id' not in self._args:
            raise ArgumentError("No iotile_id in awsiot gateway agent argument", args=args)

        self.iotile_id = int(self._args['iotile_id'], 0)

    @classmethod
    def _build_device_slug(cls, device_id):
        idhex = "{:04x}".format(device_id)

        return "d--0000-0000-0000-{}".format(idhex)

    def _extract_device_uuid(cls, slug):
        """Turn a string slug into a UUID
        """

        if len(slug) != 22:
            raise ArgumentError("Invalid device slug", slug=slug)

        hexdigits = slug[3:]
        hexdigits = hexdigits.replace('-', '')

        try:
            rawbytes = binascii.unhexlify(hexdigits)
            words = struct.unpack(">LL", rawbytes)
            return (words[0] << 32) | (words[1])
        except ValueError, exc:
            raise ArgumentError("Could not convert device slug to hex integer", slug=slug, error=str(exc))

    def start(self):
        """Start this gateway agent
        """

        self._prepare()

    def stop(self):
        if self._advertisement_callback is not None:
            self._advertisement_callback.stop()

        self.client.disconnect()

    def _prepare(self):
        self.slug = self._build_device_slug(self.iotile_id)
        self.client = OrderedAWSIOTClient(self._args)
        try:
            self.client.connect(self.slug)
        except Exception, exc:
            raise EnvironmentError("Could not connect to AWS IOT", error=str(exc))

        self.topics = MQTTTopicValidator(self.prefix + 'devices/{}'.format(self.slug))
        self._bind_topics()

        # If we should publish advertisements for the devices that we manage, set up a periodic
        # timer to manage those advertisements.
        if 'advertisement_interval' in self._args:
            advertisement_interval = self._args['advertisement_interval']
            self._advertisement_callback = tornado.ioloop.PeriodicCallback(self._publish_advertisements, int(advertisement_interval*1000), self._loop)
            self._advertisement_callback.start()
        else:
            self._logger.info("No advertisement_interval is configured, devices will not be scannable")

    def _bind_topics(self):
        self.client.subscribe(self.topics.scan_topic, self._on_scan_request, ordered=False)
        self.client.subscribe(self.topics.gateway_connect_topic, self._on_connect, ordered=False)
        self.client.subscribe(self.topics.gateway_interface_topic, self._on_interface, ordered=False)
        self.client.subscribe(self.topics.gateway_rpc_topic, self._on_rpc, ordered=False)

    def _validate_connection(self, action, uuid, key):
        """Validate that a message received for a device has the right key

        If this action is valid the corresponding internal connection id to
        be used with the DeviceManager is returned, otherwise None is returned
        and an invalid message status is published.

        Args:
            slug (string): The slug for the device we're trying to connect to
            uuid (int): The uuid corresponding to the slug
            key (string): The key passed in when this device was first connected
                to

        Returns:
            int: True if the action is allowed, otherwise False
        """

        slug = self._build_device_slug(uuid)

        if uuid not in self._connections:
            message = {}
            message['action'] = action
            message['failure_reason'] = 'Invalid uuid with no active connections'

            self._publish_status(slug, 'invalid_message', message)
            return None

        data = self._connections[uuid]
        if key != data['key']:
            message = {}
            message['action'] = action
            message['failure_reason'] = 'Invalid key'
            self._publish_status(slug, 'invalid_message', message)
            return None

        return data['connection_id']

    def _publish_status(self, slug, message_type, data):
        """Publish a status message for a device

        Args:
            slug (string): The device slug that we are publishing on behalf of
            message_type (string): The message type to publish
            data (dict): The status message data to be sent back to the caller
        """

        status_topic = self.topics.prefix + 'devices/{}/data/status'.format(slug)

        self._logger.debug("Publishing status message: (topic=%s) (message=%s)", status_topic, str(data))
        self.client.publish(status_topic, message_type, data)

    def _publish_response(self, slug, message_type, success, payload):
        """Publish a response message for a device

        Args:
            slug (string): The device slug that we are publishing on behalf of
            message_type (string): The message type to publish
            success (bool): Whether the operation was successful
            payload (dict): Whatever should be sent back to the caller 
        """

        message = {'success': success, 'payload': payload}

        resp_topic = self.topics.gateway_topic(slug, 'data/response')
        self._logger.debug("Publishing response message: (topic=%s) (message=%s)", resp_topic, str(message))
        self.client.publish(resp_topic, message_type, message)

    def _on_interface(self, sequence, topic, message_type, message):
        """Process a request to open/close an interface on an IOTile device

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        try:
            slug = None
            parts = topic.split('/')
            slug = parts[-3]
            uuid = self._extract_device_uuid(slug)
        except Exception, exc:
            self._logger.warn("Error parsing slug from connection request (slug=%s, topic=%s)", slug, topic)
            return

        try:
            message = self.topics.validate_message(['open_interface', 'close_interface'], message_type, message)
        except ValidationError, exc:
            self._publish_status(slug, 'invalid_message', exc.to_dict())
            return

        key = message['key']
        iface = message['interface']

        if message_type == 'open_interface':
            self._loop.add_callback(self._open_interface, uuid, iface, key)
        elif message_type == 'close_interface':
            self._loop.add_callback(self._close_interface, uuid, iface, key)

    def _on_rpc(self, sequence, topic, message_type, message):
        """Process a request to send an RPC to an IOTile device
        
        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        try:
            slug = None
            parts = topic.split('/')
            slug = parts[-3]
            uuid = self._extract_device_uuid(slug)
        except Exception, exc:
            self._logger.warn("Error parsing slug from rpc request (slug=%s, topic=%s)", slug, topic)
            return

        try:
            message = self.topics.validate_message(['rpc'], message_type, message)
        except ValidationError, exc:
            self._publish_status(slug, 'invalid_message', exc.to_dict())
            return

        address = message['address']
        rpc = message['rpc_id']
        payload = message['payload']
        key = message['key']
        timeout = message['timeout']

        if message_type == 'rpc':
            self._loop.add_callback(self._send_rpc, uuid, address, rpc, payload, timeout, key)

    def _on_connect(self, sequence, topic, message_type, message):
        """Process a request to connect to an IOTile device

        A connection message triggers an attempt to connect to a device,
        any error checking is done by the DeviceManager that is actually
        managing the devices.

        A disconnection message is checked to make sure its key matches
        what we except for this device and is either discarded or
        forwarded on to the DeviceManager.
        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        try:
            slug = None
            parts = topic.split('/')
            slug = parts[-3]
            uuid = self._extract_device_uuid(slug)
        except Exception, exc:
            self._logger.warn("Error parsing slug from connection request (slug=%s, topic=%s)", slug, topic)
            return

        try:
            message = self.topics.validate_message(['connect', 'disconnect'], message_type, message)
        except ValidationError, exc:
            self._publish_status(slug, 'invalid_message', exc.to_dict())
            return

        key = message['key']
        client = message['client']

        if message_type == 'connect':
            self._loop.add_callback(self._connect_to_device, uuid, key, client)
        elif message_type == 'disconnect':
            self._loop.add_callback(self._disconnect_from_device, uuid, key, client)

    @tornado.gen.coroutine
    def _send_rpc(self, uuid, address, rpc, payload, timeout, key):
        """Send an RPC to a connected device

        Args:
            uuid (int): The id of the device we're opening the interface on
            address (int): The address of the tile that we want to send the RPC to
            rpc (int): The id of the rpc that we want to send.
            payload (bytearray): The payload of arguments that we want to send
            timeout (float): The number of seconds to wait for the response
            key (string): The key to authenticate the caller
        """

        conn_id = self._validate_connection('send_rpc', uuid, key)
        if conn_id is None:
            return

        slug = self._build_device_slug(uuid)

        try:
            resp = yield self._manager.send_rpc(conn_id, address, rpc >> 8, rpc & 0xFF, str(payload), timeout)
        except Exception, exc:
            self._logger.error("Error in manager open interface: %s" % str(exc))
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        payload = {}
        if resp['success'] is False:
            payload['failure_reason'] = resp['reason']
        else:
            payload['status'] = resp['status']
            payload['payload'] = binascii.hexlify(resp['payload'])

        self._publish_response(slug, 'rpc_response', resp['success'], payload)

    @tornado.gen.coroutine
    def _open_interface(self, uuid, iface, key):
        """Open an interface on a connected device

        Args:
            uuid (int): The id of the device we're opening the interface on
            iface (string): The name of the interface that we're opening
            key (string): The key to authenticate the caller
        """

        conn_id = self._validate_connection('open_interface', uuid, key)
        if conn_id is None:
            return

        slug = self._build_device_slug(uuid)

        try:
            resp = yield self._manager.open_interface(conn_id, iface)
        except Exception, exc:
            self._logger.error("Error in manager open interface: %s" % str(exc))
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        payload = {}
        if resp['success'] is False:
            payload['failure_reason'] = resp['reason']

        self._publish_response(slug, 'open_interface_response', resp['success'], payload)

    @tornado.gen.coroutine
    def _close_interface(self, uuid, iface, key):
        """Close an interface on a connected device

        Args:
            uuid (int): The id of the device we're opening the interface on
            iface (string): The name of the interface that we're opening
            key (string): The key to authenticate the caller
        """

        conn_id = self._validate_connection('close_interface', uuid, key)
        if conn_id is None:
            return

        try:
            resp = yield self._manager.close_interface(conn_id, iface)
        except Exception, exc:
            self._logger.error("Error in manager open interface: %s" % str(exc))
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        payload = {}
        if resp['success'] is False:
            payload['failure_reason'] = resp['reason']

        slug = self._build_device_slug(uuid)
        self._publish_response(slug, 'open_interface_response', resp['success'], payload)

    @tornado.gen.coroutine
    def _disconnect_from_device(self, uuid, key, client):
        """Disconnect from a device that we have previously connected to

        Args:
            uuid (int): The unique id of the device
            key (string): A 64 byte string used to secure this connection
            client (string): The client id for who is trying to connect
                to the device.
        """

        conn_id = self._validate_connection('disconnect', uuid, key)
        if conn_id is None:
            return

        slug = self._build_device_slug(uuid)
        message = {'client': client}

        self.client.reset_sequence(self.topics.gateway_topic(slug, 'control/connect'))
        self.client.reset_sequence(self.topics.gateway_topic(slug, 'control/interface'))
        self.client.reset_sequence(self.topics.gateway_topic(slug, 'control/rpc'))

        try:
            resp = yield self._manager.disconnect(conn_id)
        except Exception, exc:
            self._logger.error("Error in manager disconnect: %s" % str(exc))
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        if resp['success']:
            del self._connections[uuid]
            message['success'] = True
        else:
            message['success'] = False
            message['failure_reason'] = resp['reason']

        self._publish_status(slug, 'disconnection_response', message)

    @tornado.gen.coroutine
    def _connect_to_device(self, uuid, key, client):
        """Connect to a device given its uuid

        Args:
            uuid (int): The unique id of the device
            key (string): A 64 byte string used to secure this connection
            client (string): The client id for who is trying to connect
                to the device.
        """

        slug = self._build_device_slug(uuid)
        message = {'client': client}

        self._logger.info("Connection attempt for device %d", uuid)

        # If someone is already connected, fail the request
        if uuid in self._connections:
            message['success'] = False
            message['failure_reason'] = 'Someone else is connected to the device'

            self._publish_status(slug, 'connection_response', message)
            return

        # Otherwise try to connect
        resp = yield self._manager.connect(uuid)
        message['success'] = resp['success']
        if resp['success']:
            conn_id = resp['connection_id']
            self._connections[uuid] = {'key': key, 'client': client, 'connection_id': conn_id}
        else:
            message['failure_reason'] = resp['reason']

        self._publish_status(slug, 'connection_response', message)

    def _on_scan_request(self, sequence, topic, message_type, message):
        """Process a request for scanning information

        Args:
            sequence (int:) The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        self._loop.add_callback(self._publish_scan_response)

    def _publish_scan_response(self):
        """Publish a scan response message

        The message contains all of the devices that are currently known
        to this agent.  Connection strings for direct connections are
        translated to what is appropriate for this agent.
        """

        devices = self._manager.scanned_devices

        message = {'devices': devices}

        # FIXME: translate the device connection string to what is appropriate
        # for this agent.

        self.client.publish(self.topics.status_topic, 'scan_response', message)

    def _publish_advertisements(self):
        devices = self._manager.scanned_devices

        for uuid, info in devices.iteritems():
            slug = self._build_device_slug(uuid)

            message = {}
            #message['expiration_time'] = str(info['expiration_time'])
            message['uuid'] = uuid
            if uuid in self._connections:
                message['user_connected'] = True
            elif 'user_connected' in info:
                message['user_connected'] = info['user_connected']
            else:
                message['user_connected'] = False

            message['connection_string'] = slug

            self.client.publish(self.topics.gateway_topic(slug, 'data/advertisement'), 'advertisement', message)
