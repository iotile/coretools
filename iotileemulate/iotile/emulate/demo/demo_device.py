"""A simple emulated reference device that includes a blank non-controller tile."""

from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.virtual.common_types import AsynchronousRPCResponse, pack_rpc_payload
from ..virtual import EmulatedPeripheralTile
from ..reference import ReferenceDevice


class DemoEmulatedTile(EmulatedPeripheralTile):
    """A basic demo emulated tile with an async rpc."""

    def __init__(self, address, name, device):
        super(DemoEmulatedTile, self).__init__(address, name, device)
        self.register_scenario('loaded_counter', self.load_counter)
        self._counter = 0


    def load_counter(self, counter):
        """Load the counter value of this device."""
        self._counter = counter

    @tile_rpc(0x8000, "L", "L")
    def async_echo(self, arg):
        """Asynchronously echo the argument number."""

        self._device.deferred_task(self._device.finish_async_rpc, self.address, 0x8000, pack_rpc_payload("L", (arg,)), sync=False)
        raise AsynchronousRPCResponse()

    @tile_rpc(0x8001, "L", "L")
    def sync_echo(self, arg):
        """Synchronously echo the argument number."""

        return [arg]

    @tile_rpc(0x8002, "", "L")
    def counter(self):
        """A counter that increments everytime it is called."""

        value = self._counter
        self._counter += 1
        return [value]


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

        peripheral = DemoEmulatedTile(11, 'abcdef', device=self)
        peripheral.declare_config_variable('test 1', 0x8000, 'uint32_t')
        peripheral.declare_config_variable('test 2', 0x8001, 'uint8_t[16]')

        self.add_tile(11, peripheral)
