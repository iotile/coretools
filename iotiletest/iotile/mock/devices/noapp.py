"""Virtual device that acts like a blank tile with just an executive installed"""

from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice


class NoAppVirtualDevice(SimpleVirtualDevice):
    """Virtual device that acts like a blank tile with just an executive loaded

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(NoAppVirtualDevice, self).__init__(1, 'NO APP')
