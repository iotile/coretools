import json
import binascii
from iotile.core.exceptions import ValidationError


class MQTTTopicValidator:
    """Canonical source of topic names for different actions.

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
    def status(self):
        """The MQTT topic used for status updates
        """

        return self.prefix + "data/status"

    @property
    def tracing(self):
        """The MQTT topic used for tracing data
        """

        return self.prefix + "data/tracing"

    @property
    def streaming(self):
        """The MQTT topic used for streaming data
        """

        return self.prefix + "data/streaming"

    @property
    def response(self):
        """The MQTT topic used for responses to rpcs and other requests
        """

        return self.prefix + "data/response"

    @property
    def action(self):
        """The MQTT topic used for sending RPCs
        """
        return self.prefix + "control/action"

    @property
    def probe(self):
        """The MQTT topic used for forcing a scan immediately
        """

        return self.prefix + "control/probe"

    @property
    def connect(self):
        """The MQTT topic used for connecting and disconnecting
        """
        return self.prefix + "control/connect"

    @property
    def gateway_connect(self):
        """The MQTT topic used for accessing devices under this gateway
        """

        return self.prefix + "devices/+/control/connect"

    @property
    def gateway_action(self):
        """The MQTT topic used for opening and closing interfaces under this gateway
        """

        return self.prefix + "devices/+/control/action"

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
