"""Base class for all emulated non-controller tiles."""

import threading
from iotile.core.exceptions import TimeoutExpiredError
from .emulated_tile import EmulatedTile
from ..constants import rpcs
from ..utilities import global_rpc


class EmulatedPeripheralTile(EmulatedTile):
    """Base class for all emulated non-controller tiles.

    Non-controller (also called peripheral tiles) wait to start until they are
    signaled to do so from a controller tile.  They also expect configuration
    information to be streamed to them in the form of config variables by the
    controller before it calls the start_application RPC that causes the
    peripheral tile to latch in the state of its config variables and start
    operation.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        name (str): The 6 character name that should be returned when this
            tile is asked for its status to allow matching it with a proxy
            object.
        device (TileBasedVirtualDevice): Device on which this tile is running.
            This parameter is not optional on EmulatedTiles.
    """

    hardware_type = 0
    firmware_version = (1, 0, 0)
    executive_version = (1, 0, 0)
    api_version = (3, 0)

    def __init__(self, address, name, device):
        EmulatedTile.__init__(self, address, name, device)

        self._app_started = threading.Event()
        self.debug_mode = False
        self.run_level = None

    @property
    def app_started(self):
        """Whether the tile's application has started running."""

        return self._app_started.is_set()

    def wait_started(self, timeout=None):
        """Wait for the application to start running."""

        flag = self._app_started.wait(timeout=timeout)
        if not flag:
            raise TimeoutExpiredError("Timeout waiting for peripheral tile to set its app_started event", address=self.address, name=self.name, timeout=timeout)

    def start(self, channel=None):
        """Start this emulated tile.

        For peripheral tiles, this triggers them to synchronously send an RPC to
        the EmulatedDevice controller registering themselves.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(EmulatedPeripheralTile, self).start(channel)

        # Register ourselves with the controller
        address, run_level, debug = self._device.rpc(8, rpcs.REGISTER_TILE, self.hardware_type, self.api_version[0], self.api_version[1], self.name,
                                                     self.firmware_version[0], self.firmware_version[1], self.firmware_version[2],
                                                     self.executive_version[0], self.executive_version[1], self.executive_version[2],
                                                     self.address - 10, 0)

        self.debug_mode = bool(debug)
        self.run_level = run_level
        self._logger.info("Tile at address %d registered itself, received address=%d, runlevel=%d and debug=%d", self.address, address, run_level, debug)

    def dump_state(self):
        """Dump the current state of this emulated tile as a dictionary.

        This function just dumps the status of the config variables.  It is designed to
        be called in a chained fashion to serialize the complete state of a tile subclass.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        state = super(EmulatedPeripheralTile, self).dump_state()
        state['app_started'] = self.app_started
        state['debug_mode'] = self.debug_mode
        state['run_level'] = self.run_level

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        super(EmulatedPeripheralTile, self).restore_state(state)

        self.debug_mode = state.get('debug_mode', False)
        self.run_level = state.get('run_level', None)

        if state.get("app_started", False):
            self._app_started.set()

    def _handle_app_started(self):
        """Hook to perform any required actions when start_application is received.

        The normal thing that a tile subclass may need to do is called is
        inspect its configuration variables and use them to set any internal
        state variables as needed.
        """

        pass

    @global_rpc(rpcs.START_APPLICATION)
    def start_application(self):
        """Latch any configuration variables and start the application."""

        self._handle_app_started()
        self._app_started.set()
