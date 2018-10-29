"""Base class for virtual devices designed to emulate physical devices."""

from __future__ import unicode_literals, absolute_import, print_function
from future.utils import viewitems
from iotile.core.exceptions import DataError
from ..virtualdevice import VirtualIOTileDevice
from .emulation_mixin import EmulationMixin
from .state_log import EmulationStateLog


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedDevice(EmulationMixin, VirtualIOTileDevice):
    """Base class for virtual devices designed to emulate physical devices.

    This class adds additional state and test scenario loading functionality
    as well as tracing of state changes on the emulated device for comparison
    and verification purposes.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (string): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    def __init__(self, iotile_id, name):
        self.state_history = EmulationStateLog()

        VirtualIOTileDevice.__init__(self, iotile_id, name)
        EmulationMixin.__init__(self, None, self.state_history)

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        state = {}

        state['tile_states'] = {}

        for address, tile in viewitems(self._tiles):
            state['tile_states'][address] = tile.dump_state()

        return state

    def restore_state(self, state):
        """Restore the current state of this emulated device.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        tile_states = state.get('tile_states', {})

        for address, tile_state in viewitems(tile_states):
            tile = self._tiles.get(address)
            if tile is None:
                raise DataError("Invalid dumped state, tile does not address", address=address)

            tile.restore_state(tile_state)
