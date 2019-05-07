"""A convenience subclass for simple virtual devices.

These devices do not include support for tiles or complex modularity but
instead just queue a few streams and/or traces when a user connects to them and
support running periodic background tasks using coroutine based workers that
are triggered on a schedule.

They are useful for writing simple, repeatable tests.
"""

from iotile.core.exceptions import ArgumentError
from ..exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from .virtualdevice_base import BaseVirtualDevice


class StandardVirtualDevice(BaseVirtualDevice):
    """A basic virtual device base class with support for tiles and scripts.

    This class implements the required controller status RPC that allows
    matching it with a proxy object.  You can define period worker functions
    that add simple interactivity using the :meth:`start_worker` method.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (str): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    __NO_EXTENSION__ = True

    def __init__(self, iotile_id):
        BaseVirtualDevice.__init__(self, iotile_id)

        self._tiles = {}
        self.script = bytearray()

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

        self.script += bytearray(chunk)

    def add_tile(self, address, tile):
        """Add a tile to handle all RPCs at a given address.
        Args:
            address (int): The address of the tile
            tile (RPCDispatcher): A tile object that inherits from RPCDispatcher
        """

        if address in self._tiles:
            raise ArgumentError("Tried to add two tiles at the same address", address=address)

        self._tiles[address] = tile

    def call_rpc(self, address, rpc_id, payload=b""):
        """Call an RPC by its address and ID.
        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes
        Returns:
            bytes: The response payload from the RPC
        """

        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        if address not in self._rpc_overlays and address not in self._tiles:
            raise TileNotFoundError("Unknown tile address, no registered handler", address=address)

        overlay = self._rpc_overlays.get(address, None)
        tile = self._tiles.get(address, None)
        if overlay is not None and overlay.has_rpc(rpc_id):
            return overlay.call_rpc(rpc_id, payload)
        elif tile is not None and tile.has_rpc(rpc_id):
            return tile.call_rpc(rpc_id, payload)

        raise RPCNotFoundError("Could not find RPC 0x%X at address %d" % (rpc_id, address))
