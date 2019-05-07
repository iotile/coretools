"""Convenience class for standard virtual tiles."""

from iotile.core.exceptions import ArgumentError
from .common_types import tile_rpc
from .virtualtile_base import BaseVirtualTile


class VirtualTile(BaseVirtualTile):
    """A standard virtual tile.

    This convenience class should be the base for most virtual tiles. It
    implements a default status rpc that allows matching proxy objects to the
    tile implementation by name.

    .. important::

        The ``__init__`` signature of all tiles that inherit from this class
        must be: ``__init__(self, address, config, device)`` where ``config``
        is a dictionary of configuration to the tile and device is a
        ``BaseVirtualDevice`` containing the tile.

        This is to allow for TileBasedDevice to uniformly find and create
        these tiles.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        name (str): The 6 character name that should be returned when this
            tile is asked for its status to allow matching it with a proxy
            object.
        device (BaseVirtualDevice) : optional, device on which this tile is running
    """

    __NO_EXTENSION__ = True

    def __init__(self, address, name, device=None):
        super(VirtualTile, self).__init__(address)
        self.name = _check_convert_name(name)

    @tile_rpc(0x0004, "", "H6sBBBB")
    def tile_status(self):
        """Required status RPC that allows matching a proxy object with a tile."""

        status = (1 << 1) | (1 << 0)  # Configured and running, not currently used but required for compat with physical tiles
        return [0xFFFF, self.name, 1, 0, 0, status]


def _check_convert_name(name):
    if not isinstance(name, bytes):
        name = name.encode('utf-8')
    if len(name) < 6:
        name += b' '*(6 - len(name))
    elif len(name) > 6:
        raise ArgumentError("Virtual tile name is too long, it must be 6 or fewer characters")

    return name
