"""Virtual device that acts like a blank tile with just an executive installed
"""

from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc, RPCInvalidIDError, RPCNotFoundError, TileNotFoundError

class NoAppVirtualDevice(VirtualIOTileDevice):
    """Virtual device that acts like a blank tile with just an executive loaded

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(NoAppVirtualDevice, self).__init__(1, 'NO APP')

    @rpc(8, 0x0004, "", "H6sBBBB")
    def status(self):
        """Return the name of the controller as a 6 byte string
        """

        status = (1 << 1) | (1 << 0) #Configured and running
        
        return [0xFFFF, self.name, 1, 0, 0, status]
