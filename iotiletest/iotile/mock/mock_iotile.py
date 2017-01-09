"""Mock IOTile device class for testing other components interactions with IOTile devices
"""

import struct
import functools
import inspect
from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc, RPCInvalidIDError, RPCNotFoundError, TileNotFoundError

class MockIOTileDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that allows capturing interactions and injecting faults

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (string): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    def __init__(self, iotile_id, name='MockCN'):
        super(MockIOTileDevice, self).__init__(iotile_id, name)

    @rpc(8, 0x0004, "", "6s")
    def controller_name(self):
        """Return the name of the controller as a 6 byte string
        """

        return [self.name]
