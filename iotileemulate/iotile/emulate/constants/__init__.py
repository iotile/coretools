"""Declarations of all important constants related to physical IOTile devices."""

from inspect import getmembers
from .errors import Error, ConfigDatabaseError, SensorLogError
from . import rpcs as rpcs
from .const_tilemanager import RunLevel, TileState
from .const_subsystems import ControllerSubsystem

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

def pack_error(subsystem, code):
    """Pack a 32-bit error code from a subsystem id and a short error code.

    Args:
        subsystem (int): The subsystem declaring the error.
        code (int): The 16-bit error code.

    Returns:
        int: The 32-bit packed error code.
    """

    return ((subsystem & 0xFFFF) << 16) | (code & 0xFFFF)


def unpack_error(error):
    """Unpack a 32-bit error code into a subsystem and short code.

    In the future this routine will attempt to match the error code and
    subsystem id with a IntEnum subclass to get nice nices when printed.

    Args:
        error (int): A packed 32-bit error code.

    Returns:
        (int, int): The subsystem ID and short error code.
    """

    return (error >> 16), (error & 0xFFFF)


__all__ = ['Error', 'ConfigDatabaseError', 'SensorLogError', 'rpcs', 'rpc_name', 'pack_error', 'unpack_error', 'RunLevel', 'TileState', 'ControllerSubsystem']
