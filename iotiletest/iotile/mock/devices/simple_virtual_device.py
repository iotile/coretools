"""Basic virtual IOTile device class for testing other components interactions with IOTile devices
"""

from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc, RPCInvalidIDError, RPCNotFoundError, TileNotFoundError

class SimpleVirtualDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that allows capturing interactions and injecting faults

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(SimpleVirtualDevice, self).__init__(1, 'Simple')

    @rpc(8, 0x0004, "", "H6sBBBB")
    def controller_name(self):
        """Return the name of the controller as a 6 byte string
        """

        status = (1 << 1) | (1 << 0) #Configured and running
        
        return [0xFFFF, self.name, 1, 0, 0, status]
