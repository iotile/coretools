import logging
import tornado.gen
import binascii
import struct
import messages
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

    @classmethod
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
        """Start this gateway agent."""

        self._prepare()

    def stop(self):
        """Stop this gateway agent."""

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

    def _bind_topics(self):
        self.client.subscribe(self.topics.probe, self._on_scan_request, ordered=False)
        self.client.subscribe(self.topics.gateway_connect, self._on_connect, ordered=False)
        self.client.subscribe(self.topics.gateway_action, self._on_action, ordered=False)

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
            int: if the action is allowed, otherwise None
        """

        if uuid not in self._connections:
            self._logger.warn("Received message for device with no connection 0x%X", uuid)
            return None

        data = self._connections[uuid]
        if key != data['key']:
            self._logger.warn("Received message for device with incorrect key, uuid=0x%X", uuid)
            return None

        return data['connection_id']

    def _publish_status(self, slug, data):
        """Publish a status message for a device

        Args:
            slug (string): The device slug that we are publishing on behalf of
            data (dict): The status message data to be sent back to the caller
        """

        status_topic = self.topics.prefix + 'devices/{}/data/status'.format(slug)

        self._logger.debug("Publishing status message: (topic=%s) (message=%s)", status_topic, str(data))
        self.client.publish(status_topic, data)

    def _publish_response(self, slug, message):
        """Publish a response message for a device

        Args:
            slug (string): The device slug that we are publishing on behalf of
            message (dict): A set of key value pairs that are used to create the message
                that is sent.
        """

        resp_topic = self.topics.gateway_topic(slug, 'data/response')
        self._logger.debug("Publishing response message: (topic=%s) (message=%s)", resp_topic, message)
        self.client.publish(resp_topic, message)

    def _on_action(self, sequence, topic, message):
        """Process a command action that we received on behalf of a device.

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message (dict): The message itself
        """

        try:
            slug = None
            parts = topic.split('/')
            slug = parts[-3]
            uuid = self._extract_device_uuid(slug)
        except Exception, exc:
            self._logger.warn("Error parsing slug in action handler (slug=%s, topic=%s)", slug, topic)
            return

        if messages.DisconnectCommand.matches(message):
            self._logger.debug("Received disconnect command for device 0x%X", uuid)
            key = message['key']
            client = message['client']
            self._loop.add_callback(self._disconnect_from_device, uuid, key, client)
        elif messages.OpenInterfaceCommand.matches(message) or messages.CloseInterfaceCommand.matches(message):
            self._logger.debug("Received %s command for device 0x%X", message['operation'], uuid)
            key = message['key']
            client = message['client']
            oper = message['operation']

            if oper == 'open_interface':
                self._loop.add_callback(self._open_interface, client, uuid, message['interface'], key)
            else:
                self._loop.add_callback(self._close_interface, client, uuid, message['interface'], key)
        elif messages.RPCCommand.matches(message):
            rpc_msg = messages.RPCCommand.verify(message)

            client = rpc_msg['client']
            address = rpc_msg['address']
            rpc = rpc_msg['rpc_id']
            payload = rpc_msg['payload']
            key = rpc_msg['key']
            timeout = rpc_msg['timeout']

            self._loop.add_callback(self._send_rpc, client, uuid, address, rpc, payload, timeout, key)
        elif messages.ScriptCommand.matches(message):
            script_msg = messages.ScriptCommand.verify(message)

            key = script_msg['key']
            client = script_msg['client']
            script = script_msg['script']

            self._loop.add_callback(self._send_script, client, uuid, script, key)
        else:
            self._logger.error("Unsupported message received (topic=%s) (message=%s)", topic, str(message))

    def _on_connect(self, sequence, topic, message):
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
        except Exception:
            self._logger.exception("Error parsing slug from connection request (slug=%s, topic=%s)", slug, topic)
            return

        if messages.ConnectCommand.matches(message):
            key = message['key']
            client = message['client']

            self._loop.add_callback(self._connect_to_device, uuid, key, client)
        else:
            self._logger.warn("Unknown message received on connect topic=%s, message=%s", topic, message)

    @tornado.gen.coroutine
    def _send_rpc(self, client, uuid, address, rpc, payload, timeout, key):
        """Send an RPC to a connected device

        Args:
            client (string): The client that sent the rpc request
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
            self._logger.error("Error in manager send rpc: %s" % str(exc))
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        payload = {'client': client, 'type': 'response', 'operation': 'rpc'}
        payload['success'] = resp['success']

        if resp['success'] is False:
            payload['failure_reason'] = resp['reason']
        else:
            payload['status'] = resp['status']
            payload['payload'] = binascii.hexlify(resp['payload'])

        self._publish_response(slug, payload)

    @tornado.gen.coroutine
    def _send_script(self, client, uuid, script, key):
        """Send a script to the connected device.

        Args:
            client (string): The client that sent the rpc request
            uuid (int): The id of the device we're opening the interface on
            script (bytes): The binary script to send to the device
            key (string): The key to authenticate the caller
        """

        conn_id = self._validate_connection('send_script', uuid, key)
        if conn_id is None:
            return

        slug = self._build_device_slug(uuid)

        try:
            resp = yield self._manager.send_script(conn_id, script, lambda x, y: self._notify_progress_async(slug, client, x, y))
        except Exception, exc:
            self._logger.exception("Error in manager send_script")
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        payload = {'client': client, 'type': 'response', 'operation': 'send_script'}
        payload['success'] = resp['success']
        if resp['success'] is False:
            payload['failure_reason'] = resp['reason']

        self._publish_response(slug, payload)

    def _notify_progress_async(self, slug, client, done_count, total_count):
        """Notify progress reporting on the status of a script download.

        Args:
            slug (string): The slug of the device that we are talking to
            client (string): The client identifier
            done_count (int): The number of items that have been finished
            total_count (int): The total number of items
        """

        status_msg = {'type': 'notification', 'operation': 'script', 'client': client, 'done_count': done_count, 'total_count': total_count}
        self._publish_status(slug, status_msg)

    @tornado.gen.coroutine
    def _open_interface(self, client, uuid, iface, key):
        """Open an interface on a connected device.

        Args:
            client (string): The client id who is requesting this operation
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
            self._logger.exception("Error in manager open interface")
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        message = {'type': 'response', 'operation': 'open_interface', 'client': client}
        message['success'] = resp['success']

        if not message['success']:
            message['failure_reason'] = resp['reason']

        self._publish_response(slug, message)

    @tornado.gen.coroutine
    def _close_interface(self, client, uuid, iface, key):
        """Close an interface on a connected device.

        Args:
            client (string): The client id who is requesting this operation
            uuid (int): The id of the device we're opening the interface on
            iface (string): The name of the interface that we're opening
            key (string): The key to authenticate the caller
        """

        conn_id = self._validate_connection('close_interface', uuid, key)
        if conn_id is None:
            return

        slug = self._build_device_slug(uuid)

        try:
            resp = yield self._manager.close_interface(conn_id, iface)
        except Exception, exc:
            self._logger.exception("Error in manager close interface")
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        message = {'type': 'response', 'operation': 'close_interface', 'client': client}
        message['success'] = resp['success']

        if not message['success']:
            message['failure_reason'] = resp['reason']

        self._publish_response(slug, message)

    @tornado.gen.coroutine
    def _disconnect_from_device(self, uuid, key, client):
        """Disconnect from a device that we have previously connected to.

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
        message = {'client': client, 'type': 'response', 'operation': 'disconnect'}

        self.client.reset_sequence(self.topics.gateway_topic(slug, 'control/connect'))
        self.client.reset_sequence(self.topics.gateway_topic(slug, 'control/action'))

        try:
            resp = yield self._manager.disconnect(conn_id)
        except Exception, exc:
            self._logger.exception("Error in manager disconnect")
            resp = {'success': False, 'reason': "Internal error: %s" % str(exc)}

        if resp['success']:
            del self._connections[uuid]
            message['success'] = True
        else:
            message['success'] = False
            message['failure_reason'] = resp['reason']

        self._logger.info("Client %s disconnected from device 0x%X", client, uuid)

        self._publish_response(slug, message)

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
        message = {'client': client, 'type': 'response', 'operation': 'connect'}

        self._logger.info("Connection attempt for device %d", uuid)

        # If someone is already connected, fail the request
        if uuid in self._connections:
            message['success'] = False
            message['failure_reason'] = 'Someone else is connected to the device'

            self._publish_status(slug, message)
            return

        # Otherwise try to connect
        resp = yield self._manager.connect(uuid)
        message['success'] = resp['success']
        if resp['success']:
            conn_id = resp['connection_id']
            self._connections[uuid] = {'key': key, 'client': client, 'connection_id': conn_id}
        else:
            message['failure_reason'] = resp['reason']

        self._connections[uuid]['report_monitor'] = self._manager.register_monitor(uuid, ['report'], self._notify_report)
        self._connections[uuid]['trace_monitor'] = self._manager.register_monitor(uuid, ['trace'], self._notify_trace)

        self._publish_status(slug, message)

    def _notify_report(self, device_uuid, event_name, report):
        """Notify that a report has been received from a device."""

        slug = self._build_device_slug(device_uuid)
        streaming_topic = self.topics.prefix + 'devices/{}/data/streaming'.format(slug)

        data = {'type': 'notification', 'operation': 'report'}

        ser = report.serialize()
        data['received_time'] = ser['received_time'].strftime("%Y%m%dT%H:%M:%S.%fZ").encode()
        data['report_origin'] = ser['origin']
        data['report_format'] = ser['report_format']
        data['report'] = binascii.hexlify(ser['encoded_report'])
        data['fragment_count'] = 1
        data['fragment_index'] = 0
        self._logger.debug("Publishing report: (topic=%s)", streaming_topic)
        self.client.publish(streaming_topic, data)

    def _notify_trace(self, device_uuid, event_name, trace):
        """Notify that we have received tracing data from a device."""

        slug = self._build_device_slug(device_uuid)
        tracing_topic = self.topics.prefix + 'devices/{}/data/tracing'.format(slug)

        data = {'type': 'notification', 'operation': 'trace'}
        data['trace'] = binascii.hexlify(trace)
        data['trace_origin'] = device_uuid

        self._logger.debug('Publishing trace: (topic=%s)', tracing_topic)
        self.client.publish(tracing_topic, data)

    def _on_scan_request(self, sequence, topic, message):
        """Process a request for scanning information

        Args:
            sequence (int:) The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (dict): The message itself
        """

        if messages.ProbeCommand.matches(message):
            self._logger.debug("Received probe message on topic %s, message=%s", topic, message)
            self._loop.add_callback(self._publish_scan_response, message['client'])
        else:
            self._logger.warn("Invalid message received on topic %s, message=%s", topic, message)

    def _publish_scan_response(self, client):
        """Publish a scan response message

        The message contains all of the devices that are currently known
        to this agent.  Connection strings for direct connections are
        translated to what is appropriate for this agent.

        Args:
            client (string): A unique id for the client that made this request
        """

        devices = self._manager.scanned_devices

        converted_devs = []
        for uuid, info in devices.iteritems():
            slug = self._build_device_slug(uuid)

            message = {}
            message['uuid'] = uuid
            if uuid in self._connections:
                message['user_connected'] = True
            elif 'user_connected' in info:
                message['user_connected'] = info['user_connected']
            else:
                message['user_connected'] = False

            message['connection_string'] = slug
            message['signal_strength'] = info['signal_strength']

            converted_devs.append({x: y for x, y in message.iteritems()})
            message['type'] = 'notification'
            message['operation'] = 'advertisement'

            self.client.publish(self.topics.gateway_topic(slug, 'data/advertisement'), message)

        probe_message = {}
        probe_message['type'] = 'response'
        probe_message['client'] = client
        probe_message['success'] = True
        probe_message['devices'] = converted_devs

        self.client.publish(self.topics.status, probe_message)
