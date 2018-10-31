"""A simple emulated reference device that includes a blank non-controller tile."""

from iotile.core.hw.virtual import EmulatedPeripheralTile
from .reference_device import ReferenceDevice


class DemoEmulatedDevice(ReferenceDevice):
    """A basic emulated device that includes a single blank tile in addition to the reference controller.

    Args:
        args (dict): A dictionary of optional creation arguments.  Currently
            supported are:
                iotile_id (int or hex string): The id of this device. This
                defaults to 1 if not specified.
    """

    STATE_NAME = "emulation_demo_device"
    STATE_VERSION = "0.1.0"

    def __init__(self, args):
        super(DemoEmulatedDevice, self).__init__(args)

        self.add_tile(10, EmulatedPeripheralTile(10, 'abcdef', device=self))
