"""Declarations of all important constants related to physical IOTile devices."""

from inspect import getmembers
from iotile.sg import DataStream
from .errors import Error, ConfigDatabaseError, SensorLogError, SensorGraphError
from . import rpcs
from . import streams
from .const_tilemanager import RunLevel, TileState
from .const_subsystems import ControllerSubsystem

_RPC_NAME_MAP = {rpc_decl.rpc_id: name for name, rpc_decl in
                 getmembers(rpcs, lambda x: isinstance(x, rpcs.RPCDeclaration))}

_STREAM_NAME_MAP = {stream_decl: name for name, stream_decl in
                    getmembers(streams, lambda x: isinstance(x, int))}


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


def stream_name(stream_id):
    """Map a stream id to a human readable name.

    The mapping process is as follows:

    If the stream id is globally known, its global name is used as <name>
    otherwise a string representation of the stream is used as <name>.

    In both cases the hex representation of the stream id is appended as a
    number:

    <name> (0x<stream id in hex>)

    Args:
        stream_id (int): An integer stream id.

    Returns:
        str: The nice name of the stream.
    """

    name = _STREAM_NAME_MAP.get(stream_id)
    if name is None:
        name = str(DataStream.FromEncoded(stream_id))

    return "{} (0x{:04X})".format(name, stream_id)


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


__all__ = ['Error', 'ConfigDatabaseError', 'SensorLogError', 'streams',
           'stream_name', 'rpcs', 'rpc_name', 'pack_error', 'unpack_error', 'RunLevel',
           'TileState', 'ControllerSubsystem']
