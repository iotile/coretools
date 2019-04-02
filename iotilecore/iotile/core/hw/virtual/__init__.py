"""Base classes for creating and interacting with virtual IOTile devices."""

from .virtualtile import VirtualTile
from .virtualdevice import VirtualIOTileDevice

from .common_types import (tile_rpc, RPCDispatcher, RPCInvalidIDError,
                           RPCNotFoundError, RPCInvalidArgumentsError,
                           RPCInvalidReturnValueError, TileNotFoundError,
                           RPCErrorCode, BusyRPCResponse, unpack_rpc_payload, pack_rpc_payload,
                           pack_rpc_response, unpack_rpc_response,
                           VALID_RPC_EXCEPTIONS)

from .virtualinterface import VirtualIOTileInterface

__all__ = ['VirtualTile', 'VirtualIOTileDevice', 'tile_rpc',
           'RPCDispatcher', 'RPCInvalidIDError', 'TileNotFoundError',
           'RPCNotFoundError', 'RPCInvalidArgumentsError', 'BusyRPCResponse',
           'RPCInvalidReturnValueError', 'RPCErrorCode', 'VirtualIOTileInterface',
           'unpack_rpc_payload', 'pack_rpc_payload', 'pack_rpc_response',
           'unpack_rpc_response',
           'VALID_RPC_EXCEPTIONS']
