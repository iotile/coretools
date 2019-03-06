import os
import binascii
import base64
import datetime
import logging
import queue
import uuid
from iotile.core.exceptions import IOTileException, ArgumentError, HardwareError
from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.hw.reports.parser import IOTileReportParser
from iotile.core.dev.registry import ComponentRegistry
from .mqtt_client import OrderedAWSIOTClient
from .topic_validator import MQTTTopicValidator
from .connection_manager import ConnectionManager
from . import messages


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
        iamsession = reg.get_config('awsiot-session', default=None)

        args = {}
        args['endpoint'] = endpoint
        args['root_certificate'] = rootcert
        args['use_websockets'] = True
        args['iam_key'] = iamuser
        args['iam_secret'] = iamsecret
        args['iam_session'] = iamsession

        self._logger = logging.getLogger(__name__)

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

        self._deferred = queue.Queue()

        self.set_config('minimum_scan_time', 5.0)
        self.set_config('probe_supported', True)
        self.set_config('probe_required', True)
        self.mtu = self.get_config('mtu', 60*1024)  # Split script payloads larger than this
        self.report_parser = IOTileReportParser()

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

        conn_message = {'type': 'command', 'operation': 'connect', 'key': key, 'client': name}
        context = {'key': key, 'slug': connection_string, 'topics': topics}

        self.conns.begin_connection(connection_id, connection_string, callback, context, self.get_config('default_timeout'))

        self._bind_topics(topics)

        try:
            self.client.publish(topics.connect, conn_message)
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
        disconn_message = {'key': context['key'], 'client': self.name, 'type': 'command', 'operation': 'disconnect'}

        self.client.publish(topics.action, disconn_message)

    def send_script_async(self, conn_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script. The callback will be called as
                callback(connection_id, adapter_id, success, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        try:
            context = self.conns.get_context(conn_id)
        except ArgumentError:
            callback(conn_id, self.id, False, "Could not find connection information")
            return

        topics = context['topics']
        context['progress_callback'] = progress_callback

        self.conns.begin_operation(conn_id, 'script', callback, 60.0)

        chunks = 1
        if len(data) > self.mtu:
            chunks = len(data) // self.mtu
            if len(data) % self.mtu != 0:
                chunks += 1

        # Send the script out possibly in multiple chunks if it's larger than our maximum transmit unit
        for i in range(0, chunks):
            start = i*self.mtu
            chunk = data[start:start + self.mtu]
            encoded = base64.standard_b64encode(chunk)

            script_message = {'key': context['key'], 'client': self.name, 'type': 'command', 'operation': 'send_script',
                              'script': encoded, 'fragment_count': chunks, 'fragment_index': i}

            self.client.publish(topics.action, script_message)

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            address (int): the address of the tile that we wish to send the RPC to
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

        rpc_message = {'key': context['key'], 'client': self.name, 'type': 'command', 'operation': 'rpc',
                       'address': address, 'rpc_id': rpc_id, 'payload': encoded_payload, 'timeout': timeout}

        self.client.publish(topics.action, rpc_message)

    def _open_rpc_interface(self, conn_id, callback):
        """Enable RPC interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        self._open_interface(conn_id, 'rpc', callback)

    def _open_streaming_interface(self, conn_id, callback):
        """Enable streaming interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        self._open_interface(conn_id, 'streaming', callback)

    def _open_tracing_interface(self, conn_id, callback):
        """Enable tracing interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        self._open_interface(conn_id, 'tracing', callback)

    def _open_script_interface(self, conn_id, callback):
        """Enable script interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        self._open_interface(conn_id, 'script', callback)

    def _open_interface(self, conn_id, iface, callback):
        """Open an interface on this device

        Args:
            conn_id (int): the unique identifier for the connection
            iface (string): the interface name to open
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

        open_iface_message = {'key': context['key'], 'type': 'command', 'operation': 'open_interface', 'client': self.name, 'interface': iface}
        self.client.publish(topics.action, open_iface_message)

    def stop_sync(self):
        """Synchronously stop this adapter
        """

        conn_ids = self.conns.get_connections()

        # If we have any open connections, try to close them here before shutting down
        for conn in list(conn_ids):
            try:
                self.disconnect_sync(conn)
            except HardwareError:
                pass

        self.client.disconnect()
        self.conns.stop()

    def probe_async(self, callback):
        """Probe for visible devices connected to this DeviceAdapter.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        topics = MQTTTopicValidator(self.prefix)
        self.client.publish(topics.probe, {'type': 'command', 'operation': 'probe', 'client': self.name})
        callback(self.id, True, None)

    def periodic_callback(self):
        """Periodically help maintain adapter internal state
        """

        while True:
            try:
                action = self._deferred.get(False)
                action()
            except queue.Empty:
                break
            except Exception:
                self._logger.exception('Exception in periodic callback')

    def _bind_topics(self, topics):
        """Subscribe to all the topics we need to communication with this device

        Args:
            topics (MQTTTopicValidator): The topic validator for this device that
                we are connecting to.
        """

        # FIXME: Allow for these subscriptions to fail and clean up the previous ones
        # so that this function is atomic

        self.client.subscribe(topics.status, self._on_status_message)
        self.client.subscribe(topics.tracing, self._on_trace)
        self.client.subscribe(topics.streaming, self._on_report)
        self.client.subscribe(topics.response, self._on_response_message)

    def _unbind_topics(self, topics):
        """Unsubscribe to all of the topics we needed for communication with device

        Args:
            topics (MQTTTopicValidator): The topic validator for this device that
                we have connected to.
        """

        self.client.unsubscribe(topics.status)
        self.client.unsubscribe(topics.tracing)
        self.client.unsubscribe(topics.streaming)
        self.client.unsubscribe(topics.response)

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

    def _on_advertisement(self, sequence, topic, message):
        try:
            # FIXME: We need a global topic validator to validate these messages
            # message = self.topics.validate_message(['advertisement'], message_type, message)

            del message['operation']
            del message['type']
            self._trigger_callback('on_scan', self.id, message, 60.) # FIXME: Get the timeout from somewhere
        except IOTileException as exc:
            pass

    def _on_report(self, sequence, topic, message):
        """Process a report received from a device.

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message (dict): The message itself
        """

        try:
            conn_key = self._find_connection(topic)
            conn_id = self.conns.get_connection_id(conn_key)
        except ArgumentError:
            self._logger.warn("Dropping report message that does not correspond with a known connection, topic=%s", topic)
            return

        try:
            rep_msg = messages.ReportNotification.verify(message)

            serialized_report = {}
            serialized_report['report_format'] = rep_msg['report_format']
            serialized_report['encoded_report'] = rep_msg['report']
            serialized_report['received_time'] = datetime.datetime.strptime(rep_msg['received_time'].encode().decode(), "%Y%m%dT%H:%M:%S.%fZ")

            report = self.report_parser.deserialize_report(serialized_report)
            self._trigger_callback('on_report', conn_id, report)
        except Exception:
            self._logger.exception("Error processing report conn_id=%d", conn_id)

    def _on_trace(self, sequence, topic, message):
        """Process a trace received from a device.

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message (dict): The message itself
        """

        try:
            conn_key = self._find_connection(topic)
            conn_id = self.conns.get_connection_id(conn_key)
        except ArgumentError:
            self._logger.warn("Dropping trace message that does not correspond with a known connection, topic=%s", topic)
            return

        try:
            tracing = messages.TracingNotification.verify(message)
            self._trigger_callback('on_trace', conn_id, tracing['trace'])
        except Exception:
            self._logger.exception("Error processing trace conn_id=%d", conn_id)

    def _on_status_message(self, sequence, topic, message):
        """Process a status message received

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message (dict): The message itself
        """

        self._logger.debug("Received message on (topic=%s): %s" % (topic, message))

        try:
            conn_key = self._find_connection(topic)
        except ArgumentError:
            self._logger.warn("Dropping message that does not correspond with a known connection, message=%s", message)
            return

        if messages.ConnectionResponse.matches(message):
            if self.name != message['client']:
                self._logger.debug("Connection response received for a different client, client=%s, name=%s", message['client'], self.name)
                return

            self.conns.finish_connection(conn_key, message['success'], message.get('failure_reason', None))
        else:
            self._logger.warn("Dropping message that did not correspond with a known schema, message=%s", message)

    def _on_response_message(self, sequence, topic, message):
        """Process a response message received

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message (dict): The message itself
        """

        try:
            conn_key = self._find_connection(topic)
            context = self.conns.get_context(conn_key)
        except ArgumentError:
            self._logger.warn("Dropping message that does not correspond with a known connection, message=%s", message)
            return

        if 'client' in message and message['client'] != self.name:
            self._logger.debug("Dropping message that is for another client %s, we are %s", message['client'], self.name)

        if messages.DisconnectionResponse.matches(message):
            self.conns.finish_disconnection(conn_key, message['success'], message.get('failure_reason', None))
        elif messages.OpenInterfaceResponse.matches(message):
            self.conns.finish_operation(conn_key, message['success'], message.get('failure_reason', None))
        elif messages.RPCResponse.matches(message):
            rpc_message = messages.RPCResponse.verify(message)
            self.conns.finish_operation(conn_key, rpc_message['success'], rpc_message.get('failure_reason', None), rpc_message.get('status', None), rpc_message.get('payload', None))
        elif messages.ProgressNotification.matches(message):
            progress_callback = context.get('progress_callback', None)
            if progress_callback is not None:
                progress_callback(message['done_count'], message['total_count'])
        elif messages.ScriptResponse.matches(message):
            if 'progress_callback' in context:
                del context['progress_callback']

            self.conns.finish_operation(conn_key, message['success'], message.get('failure_reason', None))
        elif messages.DisconnectionNotification.matches(message):
            try:
                conn_key = self._find_connection(topic)
                conn_id = self.conns.get_connection_id(conn_key)
            except ArgumentError:
                self._logger.warn("Dropping disconnect notification that does not correspond with a known connection, topic=%s", topic)
                return

            self.conns.unexpected_disconnect(conn_key)
            self._trigger_callback('on_disconnect', self.id, conn_id)
        else:
            self._logger.warn("Invalid response message received, message=%s", message)
