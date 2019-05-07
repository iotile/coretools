"""Basic virtual IOTile device class for testing other components interactions with IOTile devices"""

import random
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice, rpc


class SensorGraphTestDevice(SimpleVirtualDevice):
    """Mock IOTileDevice that can be used to test sensor graphs.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(SensorGraphTestDevice, self).__init__(1, 'Simple')

    @rpc(8, 0x8000, "", "L")
    def random_int(self):
        """Return a random int in the range [0, 100)."""

        return [random.randrange(0, 100)]

    @rpc(11, 0x8001, "", "L")
    def return_fixed_int(self):
        """Return the fixed intger 42."""

        return [42]
