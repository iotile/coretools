"""Virtual device for testing app matching."""

from iotile.core.hw.virtual import SimpleVirtualDevice, rpc


class AppInfoVirtualDevice(SimpleVirtualDevice):
    """Virtual device that acts like a blank tile with just an executive loaded.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            None are supported.
    """

    def __init__(self, args):
        super(AppInfoVirtualDevice, self).__init__(1, 'abcdef')

    @rpc(8, 0x1008, "", "12xLL")
    def app_os_info(self):
        """Return os/app info for this device."""

        os_tag = 2000
        os_version = (1, 2)
        app_tag = 2100
        app_version = (2, 3)

        os_info = (os_version[0] << 26 | os_version[1] << 20 | os_tag)
        app_info = (app_version[0] << 26 | app_version[1] << 20 | app_tag)

        return [os_info, app_info]
