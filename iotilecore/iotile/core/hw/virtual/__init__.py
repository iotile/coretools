"""Base classes for creating and interacting with virtual IOTile devices."""

from .virtualtile import VirtualTile
from .virtualtile_base import BaseVirtualTile
from .virtualdevice_base import BaseVirtualDevice
from .virtualdevice_standard import StandardVirtualDevice
from .virtualdevice_simple import SimpleVirtualDevice

from .common_types import (tile_rpc, RPCDispatcher, RPCInvalidIDError,
                           RPCNotFoundError, RPCInvalidArgumentsError,
                           RPCInvalidReturnValueError, TileNotFoundError,
                           RPCErrorCode, BusyRPCResponse, unpack_rpc_payload, pack_rpc_payload,
                           pack_rpc_response, unpack_rpc_response,
                           VALID_RPC_EXCEPTIONS, rpc)

__all__ = ['BaseVirtualTile', 'VirtualTile', 'BaseVirtualDevice', 'StandardVirtualDevice', 'SimpleVirtualDevice', 'tile_rpc', 'rpc',
           'RPCDispatcher', 'RPCInvalidIDError', 'TileNotFoundError',
           'RPCNotFoundError', 'RPCInvalidArgumentsError', 'BusyRPCResponse',
           'RPCInvalidReturnValueError', 'RPCErrorCode',
           'unpack_rpc_payload', 'pack_rpc_payload', 'pack_rpc_response',
           'unpack_rpc_response',
           'VALID_RPC_EXCEPTIONS']
