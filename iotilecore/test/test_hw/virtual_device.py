"""Virtual device for testing virtual device loading
"""

from iotile.core.hw.virtual import SimpleVirtualDevice, rpc


class BasicVirtualDevice(SimpleVirtualDevice):
    """Virtual device that acts like a blank tile with just an executive loaded

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(BasicVirtualDevice, self).__init__(1, 'abcdef')
