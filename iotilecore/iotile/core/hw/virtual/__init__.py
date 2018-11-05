"""Base classes for creating and interacting with virtual IOTile devices."""

from .virtualtile import VirtualTile
from .virtualdevice import VirtualIOTileDevice

from .common_types import (tile_rpc, RPCDispatcher, RPCInvalidIDError,
                           RPCNotFoundError, RPCInvalidArgumentsError,
                           RPCInvalidReturnValueError, TileNotFoundError,
                           RPCErrorCode)
from .virtualinterface import VirtualIOTileInterface

__all__ = ['VirtualTile', 'VirtualIOTileDevice', 'tile_rpc',
           'RPCDispatcher', 'RPCInvalidIDError', 'TileNotFoundError',
           'RPCNotFoundError', 'RPCInvalidArgumentsError',
           'RPCInvalidReturnValueError', 'RPCErrorCode', 'VirtualIOTileInterface']
