"""A general purpose virtual device base class.

This base class supports adding tiles to your virtual device containing RPCs.
Each tile is assigned an address and can have many RPCs tagged with
``@tile_rpc`` decorators.

Unlike :class:`SimpleVirtualDevice`, there is no way to define an RPC without
putting it inside of a tile first.  This makes this class slightly more
complicated to use when you only want to implement a very small number of RPCs
and are not interested in reusing your RPC implementations.  For those cases,
:class:`SimpleVirtualDevice` is a better base class to inherit from.
"""

import inspect
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities import SharedLoop
from ..exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from .virtualdevice_base import BaseVirtualDevice


class StandardVirtualDevice(BaseVirtualDevice):
    """A basic virtual device base class with support for tiles and scripts.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        loop (BackgroundEventLoop): The loop we should use for running background
            tasks. Defaults to the global SharedLoop.
    """

    __NO_EXTENSION__ = True

    def __init__(self, iotile_id, *, loop=SharedLoop):
        BaseVirtualDevice.__init__(self, iotile_id, loop=loop)

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

    async def async_rpc(self, address, rpc_id, payload=b""):
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

        if address not in self._tiles:
            raise TileNotFoundError("Unknown tile address, no registered handler", address=address)

        tile = self._tiles.get(address)
        if tile is not None and tile.has_rpc(rpc_id):
            resp = tile.call_rpc(rpc_id, payload)
            if inspect.isawaitable(resp):
                resp = await resp

            return resp

        raise RPCNotFoundError("Could not find RPC 0x%X at address %d" % (rpc_id, address))
