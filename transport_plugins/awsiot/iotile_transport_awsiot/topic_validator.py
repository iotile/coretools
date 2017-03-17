import json
import binascii
from iotile.core.exceptions import ValidationError

class MQTTTopicValidator(object):
    """Canonical source of topic names for different actions

    This class returns the correct topic names for connection
    requests, rpcs, scripts, etc.

    Args:
        prefix (string): (optional) The MQTT topic prefix to use, which should
            end in a /.  If it does not, a trailing / is added
    """

    def __init__(self, prefix=""):
        prefix = str(prefix)

        if len(prefix) > 0 and prefix[-1] != '/':
            prefix = prefix + '/'

        self.prefix = prefix
        self.key = None
        self.client = None

    def lock(self, key, client):
        """Set the key that will be used to ensure messages come from one party

        Args:
            key (string): The key used to validate future messages
            client (string): A string that will be returned to indicate who
                locked this device.
        """

        self.key = key
        self.client = client

    def unlock(self):
        self.key = None
        self.client = None

    @property
    def locked(self):
        return self.key is not None

    @property
    def status_topic(self):
        """The MQTT topic used for status updates
        """

        return self.prefix + "data/status"

    @property
    def response_topic(self):
        """The MQTT topic used for responses to rpcs and other requests
        """

        return self.prefix + "data/response"

    @property
    def rpc_topic(self):
        """The MQTT topic used for sending RPCs
        """
        return self.prefix + "control/rpc"

    @property
    def scan_topic(self):
        """The MQTT topic used for forcing a scan immediately
        """

        return self.prefix + "control/scan"

    @property
    def connect_topic(self):
        """The MQTT topic used for connecting and disconnecting
        """
        return self.prefix + "control/connect"

    @property
    def interface_topic(self):
        """The MQTT topic used for opening and closing interfaces
        """
        return self.prefix + "control/interface"

    @property
    def gateway_connect_topic(self):
        """The MQTT topic used for accessing devices under this gateway
        """

        return self.prefix + "devices/+/control/connect"

    @property
    def gateway_interface_topic(self):
        """The MQTT topic used for opening and closing interfaces under this gateway
        """

        return self.prefix + "devices/+/control/interface"

    @property
    def gateway_rpc_topic(self):
        """The MQTT topic used for opening and closing interfaces under this gateway
        """

        return self.prefix + "devices/+/control/rpc"

    def gateway_topic(self, slug, postfix):
        """Return a properly prefixed gateway topic

        Constructs a string of the form:

        prefix/devices/<slug>/postfix

        Args:
            slug (string): The device slug we are referencing
            postfix (string): The path after the slug, without a slash

        Returns:
            string: The fully qualified topic name
        """

        return self.prefix + 'devices/{}/{}'.format(slug, postfix)

    def validate_message(self, valid_types, message_type, message):
        """Validate and a message according to its type

        Looks for a validate_{type}_message function and runs it to
        validate the message.  Throws a ValidationError if the message
        is invalid.

        Args:
            valid_types (iterable): A list of valid message types
            message_type (string): The type of the packet received
            message (dict): The message itself

        Returns:
            dict: The parsed message

        Raises:
            ValidationError: when the message fails validation for some reason
        """

        if message_type not in valid_types:
            raise ValidationError("Invalid message type", valid_types=valid_types, message_type=message_type)

        validator_name = '_validate_{}_message'.format(message_type)

        if not hasattr(self, validator_name):
            raise ValidationError("No validator registered for message type", message_type=message_type)

        validator = getattr(self, validator_name)
        return validator(message)

    def _validate_connect_message(self, message):
        """Validate that a connection message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'key' not in message or 'client' not in message:
            raise ValidationError("Missing parameter in connection request", required=['key', 'client'], message=message)

        try:
            message['key'] = str(message['key'])
            message['client'] = str(message['client'])
        except ValueError:
            raise ValidationError("Could not convert message properties to string")

        return message

    def _validate_advertisement_message(self, message):
        """Validate that an advertisement message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'uuid' not in message or 'connection_string' not in message:
            raise ValidationError("Missing parameter in advertisement message", required=['uuid', 'connection_string'], message=message)

        return message

    def _validate_scan_message(self, message):
        """Validate that an scan request message has the right schema

        There is no fixed format for scan request messages
        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        return message

    def _validate_scan_response_message(self, message):
        """Validate that a scan response message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'devices' not in message:
            raise ValidationError("No devices key in scan response message", message=message)
        elif not isinstance(message['devices']):
            raise ValidationError("Devices key is not a dictionary in scan response message", message=message)
        
        return message

    def _validate_rpc_message(self, message):
        """Validate that an rpc message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'key' not in message or 'client' not in message:
            raise ValidationError("Missing parameter in rpc message", required=['key', 'client'], message=message)

        if 'address' not in message or 'rpc_id' not in message or 'payload' not in message:
            raise ValidationError("Missing parameter in rpc message", required=['address', 'rpc_id', 'payload'], message=message)
        if 'timeout' not in message:
            raise ValidationError("Missing parameter in rpc message", required=['timeout'], message=message)

        try:
            message['address'] = int(message['address'])
            message['rpc_id'] = int(message['rpc_id'])
            message['timeout'] = float(message['timeout'])
            message['payload'] = bytearray(binascii.unhexlify(message['payload']))
        except ValueError, exc:
            raise ValidationError("Could not convert rpc message to appropriate data types", message=message, error=str(exc))

        return message

    def _validate_rpc_response_message(self, message):
        """Validate that an rpc response message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'success' not in message or 'payload' not in message:
            raise ValidationError("Missing parameter in rpc response message", required=['success', 'payload'], message=message)

        try:
            payload = message['payload']

            if 'status' not in payload or 'payload' not in payload:
                raise ValidationError("Missing parameter in rpc response message payload", required=['status', 'payload'], message=message)

            payload['payload'] = bytearray(binascii.unhexlify(payload['payload']))
        except KeyError:
            raise ValidationError("payload is not a dictionary in rpc_response", required_keys=['success', 'payload'], message=message)
        except TypeError:
            raise ValidationError("payload is not a valid dictionary in rpc_response", message=message)
        except ValueError:
            raise ValidationError("could not unpack response payload", message=message)

        return message

    def _validate_open_interface_message(self, message):
        """Validate that an open_interface message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'key' not in message or 'client' not in message:
            raise ValidationError("Missing parameter in open_interface message", required=['key', 'client'], message=message)

        if 'interface' not in message:
            raise ValidationError("Missing parameter in open_interface message", required=['interface'], message=message)            

        return message

    def _validate_close_interface_message(self, message):
        """Validate that a close_interface message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'key' not in message or 'client' not in message:
            raise ValidationError("Missing parameter in close_interface message", required=['key', 'client'], message=message)

        if 'interface' not in message:
            raise ValidationError("Missing parameter in close_interface message", required=['interface'], message=message)            

        return message

    def _validate_disconnect_message(self, message):
        """Validate that a disconnect message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'key' not in message or 'client' not in message:
            raise ValidationError("Missing parameter in disconnect message", required=['key', 'client'], message=message)

        return message

    def _validate_heartbeat_message(self, message):
        """Validate that a hearbeat message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'timestamp' not in message:
            raise ValidationError("Missing timestamp key in heartbeat", message=message)

        if 'locked' not in message:
            raise ValidationError("Missing locked key in heartbeat", message=message)

        if message['locked']:
            if 'connected_user' not in message:
                raise ValidationError("Missing connected_user key in heartbeat", message=message)

        return message

    def _validate_disconnection_response_message(self, message):
        """Validate that a disconnection response message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'success' not in message:
            raise ValidationError('Missing parameter success', message=message)

        if 'client' not in message:
            raise ValidationError("No client in disconnection response", message=message)

        success = message['success']
        if success is False and 'failure_reason' not in message:
            raise ValidationError("No failure_reason in failed disconnection response", message=message)

        return message

    def _validate_connection_response_message(self, message):
        """Validate that a connection response message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'success' not in message:
            raise ValidationError('Missing parameter success', message=message)

        if 'client' not in message:
            raise ValidationError("No client in connection response", message=message)

        success = message['success']
        if success is False and 'failure_reason' not in message:
            raise ValidationError("No failure_reason in failed connection response", message=message)

        return message

    def _validate_open_interface_response_message(self, message):
        """Validate that an open interface response message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'success' not in message or 'payload' not in message:
            raise ValidationError('Missing parameter success and payload', message=message)

        success = message['success']
        payload = message['payload']
        if success is False and 'reason' not in payload:
            raise ValidationError("No failure reason in failed open interface response", message=message)

        return message

    def _validate_close_interface_response_message(self, message):
        """Validate that an close interface response message has the right schema

        Args:
            message (dict): The message that we are validating

        Returns:
            dict: The validated message, possibly with some additional decoding
                performed.
        """

        if 'success' not in message or 'payload' not in message:
            raise ValidationError('Missing parameter success and payload', message=message)

        success = message['success']
        payload = message['payload']
        if success is False and 'reason' not in payload:
            raise ValidationError("No failure reason in failed close interface response", message=message)

        return message
