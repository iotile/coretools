"""Base class for virtual tiles designed to emulate physical tiles."""

from __future__ import unicode_literals, absolute_import, print_function

from iotile.core.exceptions import ArgumentError
from ..virtualtile import VirtualTile
from .emulated_device import EmulatedDevice
from .emulation_mixin import EmulationMixin


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedTile(EmulationMixin, VirtualTile):
    """Base class for virtual tiles designed to emulate physical tiles.

    This class adds additional state and test scenario loading functionality
    as well as tracing of state changes on the emulated device for comparison
    and verification purposes.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        name (str): The 6 character name that should be returned when this
            tile is asked for its status to allow matching it with a proxy
            object.
        device (TileBasedVirtualDevice): Device on which this tile is running.
            This parameter is not optional on EmulatedTiles.
    """

    def __init__(self, address, name, device):
        if not isinstance(device, EmulatedDevice):
            raise ArgumentError("You can only add an EmulatedTile to an EmulatedDevice", device=device)

        VirtualTile.__init__(self, address, name, device)
        EmulationMixin.__init__(self, address, device.state_history)
