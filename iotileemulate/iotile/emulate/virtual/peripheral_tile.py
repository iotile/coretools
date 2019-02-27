"""Base class for all emulated non-controller tiles."""

from iotile.core.hw.virtual import tile_rpc
from .emulated_tile import EmulatedTile
from ..constants import rpcs, RunLevel


class EmulatedPeripheralTile(EmulatedTile):
    """Base class for all emulated non-controller tiles.

    Non-controller (also called peripheral) tiles wait to start until they are
    signaled to do so from a controller tile.  They also expect configuration
    information to be streamed to them in the form of config variables by the
    controller before it calls the start_application RPC that causes the
    peripheral tile to latch in the state of its config variables and start
    operation.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        device (TileBasedVirtualDevice): Device on which this tile is running.
            This parameter is not optional on EmulatedTiles.
    """

    __NO_EXTENSION__ = True

    def __init__(self, address, device):
        EmulatedTile.__init__(self, address, device)

        self._registered = device.emulator.create_event()
        self._start_received = device.emulator.create_event()
        self._hosted_app_running = device.emulator.create_event()

        self.debug_mode = False
        self.run_level = None

    async def _application_main(self):
        """The placeholder for the main application loop.

        This method should be overwritten by subclasses of
        EmulatedPeripheralTile with their background main loop task.  This
        coroutine is equivalent to the main() C function in a physical tile's
        firmware.

        This coroutine should loop forever.  It will not be restarted if it
        returns unless reset() is called on the tile.

        If you override this method, you **must set self.initialized()** once
        you have initialized any required state, otherwise the emulation will
        hang waiting for your tile to indicate that it has been initialized.
        """

        self.initialized.set()

    async def _reset_vector(self):
        """Main background task for the tile executive.

        The tile executive is in charge registering the tile with the
        controller and then handing control over to the tile's application
        firmware after proper configuration values have been received.
        """

        self._logger.info("Tile %s at address %d is starting from reset", self.name, self.address)

        try:
            address, run_level, debug = await self._device.emulator.await_rpc(8, rpcs.REGISTER_TILE, *self._registration_tuple())
        except:
            self._logger.exception("Error registering tile: address=%d, name=%s", self.address, self.name)
            raise

        self.debug_mode = bool(debug)
        self.run_level = run_level
        self._logger.info("Tile at address %d registered itself, received address=%d, runlevel=%d and debug=%d", self.address, address, run_level, debug)

        self._registered.set()

        # If we are in safe mode we do not run the main application
        # loop.
        if run_level == RunLevel.SAFE_MODE:
            self.initialized.set()
            return

        if run_level == RunLevel.START_ON_COMMAND:
            await self._start_received.wait()

        self._hosted_app_running.set()
        await self._application_main()

    def _registration_tuple(self):
        return (self.hardware_type, self.api_version[0], self.api_version[1], self.name,
                self.firmware_version[0], self.firmware_version[1], self.firmware_version[2],
                self.executive_version[0], self.executive_version[1], self.executive_version[2],
                self.address - 10, 0)

    def _handle_reset(self):
        """Reset this tile.

        This process needs to trigger the peripheral tile to reregister itself
        with the controller and get new configuration variables.  It also
        needs to clear app_running.
        """

        self._registered.clear()
        self._start_received.clear()
        self._hosted_app_running.clear()

        super(EmulatedPeripheralTile, self)._handle_reset()

    def dump_state(self):
        """Dump the current state of this emulated tile as a dictionary.

        This function just dumps the status of the config variables.  It is
        designed to be called in a chained fashion to serialize the complete
        state of a tile subclass.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        state = super(EmulatedPeripheralTile, self).dump_state()
        state['app_started'] = self._hosted_app_running.is_set()
        state['debug_mode'] = self.debug_mode
        state['run_level'] = self.run_level

        return state

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        super(EmulatedPeripheralTile, self).restore_state(state)

        self.debug_mode = state.get('debug_mode', False)
        self.run_level = state.get('run_level', None)

        if state.get('app_started', False):
            self._hosted_app_running.set()

    @tile_rpc(*rpcs.START_APPLICATION)
    def start_application(self):
        """Latch any configuration variables and start the application."""

        self._start_received.set()
