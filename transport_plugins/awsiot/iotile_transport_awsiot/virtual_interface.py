import time
import json
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import EnvironmentError, HardwareError
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
        self.slug = None
        self.args = args

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
        self._bind_topics()

    def _bind_topics(self):
        """Subscribe to all the topics needed for interaction with this device
        """

        print(self._rpc_channel())

        self.client.subscribe(self._rpc_channel(), self._on_rpc_message)

    def process(self):
        """Periodic nonblocking processes
        """

        now = time.time()
        if now < self._last_heartbeat:
            self._last_heartbeat = now
        elif (now - self._last_heartbeat) > self.HeartbeatInterval:
            self.client.publish(self._status_channel(), 'heartbeat', "Timestamp: %s" % str(now))
            self._last_heartbeat = now

        super(AWSIOTVirtualInterface, self).process()

    def stop(self):
        """Safely shut down this interface
        """

        if self.client is not None:
            self.client.disconnect()

    def _on_rpc_message(self, sequence, topic, message_type, message):
        """Process a received RPC packet

        Args:
            sequence (int): The sequence number of the packet received
            topic (string): The topic this message was received on
            message_type (string): The type of the packet received
            message (string): The message itself
        """

        if message_type != 'rpc':
            print("Unknown RPC packet received: " % message_type)
            return

        try:
            parsed = json.loads(message)
        except ValueError:
            print("Invalid RPC packet received, could not decode json")
            return

        print(parsed)

    def _status_channel(self):
        return "devices/{}/data/status".format(self.slug)

    def _rpc_channel(self):
        return "devices/{}/control/rpc".format(self.slug)
