"""A simple emulated reference device that includes a blank non-controller tile."""

from ..virtual import EmulatedPeripheralTile
from ..reference import ReferenceDevice


class DemoEmulatedDevice(ReferenceDevice):
    """A basic emulated device that includes a single blank tile in addition to the reference controller.

    The blank tile in slot 1 has module name abcdef and the following two config variables declared
    to allow for testing config variable usage and streaming:

    - 0x8000: uint32_t
    - 0x8001: uint8_t[16]

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

        peripheral = EmulatedPeripheralTile(11, 'abcdef', device=self)
        peripheral.declare_config_variable('test 1', 0x8000, 'uint32_t')
        peripheral.declare_config_variable('test 2', 0x8001, 'uint8_t[16]')

        self.add_tile(11, peripheral)
