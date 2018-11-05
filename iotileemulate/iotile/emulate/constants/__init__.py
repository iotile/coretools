"""Declarations of all important constants related to physical IOTile devices."""

from inspect import getmembers
from .errors import Error, ConfigDatabaseError
from . import rpcs as rpcs
from .const_tilemanager import RunLevel, TileState


_RPC_NAME_MAP = {rpc_decl.rpc_id: name for name, rpc_decl in
                 getmembers(rpcs, lambda x: isinstance(x, rpcs.RPCDeclaration))}

def rpc_name(rpc_id):
    """Map an RPC id to a string name.

    This function looks the RPC up in a map of all globally declared RPCs,
    and returns a nice name string.  if the RPC is not found in the global
    name map, returns a generic name string such as 'rpc 0x%04X'.

    Args:
        rpc_id (int): The id of the RPC that we wish to look up.

    Returns:
        str: The nice name of the RPC.
    """

    name = _RPC_NAME_MAP.get(rpc_id)
    if name is None:
        name = 'RPC 0x%04X' % rpc_id

    return name


__all__ = ['Error', 'ConfigDatabaseError', 'rpcs', 'rpc_name', 'RunLevel', 'TileState']
