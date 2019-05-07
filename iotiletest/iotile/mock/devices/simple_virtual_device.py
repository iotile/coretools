"""Basic virtual IOTile device class for testing other components interactions with IOTile devices"""

from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice


class SimpleVirtualDevice(SimpleVirtualDevice):
    """Mock IOTileDevice that allows capturing interactions and injecting faults

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(SimpleVirtualDevice, self).__init__(1, 'Simple')
