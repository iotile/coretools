"""All well-known globally defined RPCS including their RPC identifier and signatures.

All of the RPC declarations in this module are of type RPCDeclaration and include
a detailed description of their expected semantics in the associated docstring.

The RPCDeclaration can be directly passed to the EmulatedDevice.rpc or
EmulatedDevice.deferred_rpc functions as `rpc_id`, in which case arg_format
and resp_format keyword arguments can be omitted as they will be inferred from
the RPCDeclaration itself.
"""

#pylint:disable=wildcard-import,unused-wildcard-import;This is designed to a single place for all RPCS.
from iotile.core.hw.virtual import RPCDeclaration
from .rpc_tilemanager import *
from .rpc_config_database import *
from .rpc_config_variables import *
from .rpc_sensorlog import *
from .rpc_sensorgraph import *
from .rpc_clockmanager import *
from .rpc_controller import *


# Tile Lifecycle Related RPCS

RESET = RPCDeclaration(1, "", "")
"""Immediately reset the tile.

This RPC will never complete in the normal sense because the tile will reset
in the middle of executing it.   Callers should expect to receive a
ModuleNotFound error or other atypical response code from this RPC.  There is
not a straightforward, portable way to determine the response code caused by
the tile resetting from a response code caused by an issue running this RPC.
"""

HARDWARE_VERSION = RPCDeclaration(2, "", "10s")
"""Get a hardware identification string.

This RPC returns a string of up to 10 bytes (padded with null bytes) to
a fixed 10 byte length that contains a hardware identification string.
The meaning of the string is opaque and defined by the firmware that is
returning this string.  The typical use of this value is to determine
what tile hardware is running if a given tile firmware is compatible
with multiple boards.

Returns:
  - char[10]: A utf-8 hardware string padded with null bytes to 10
    bytes.
"""

TILE_STATUS = RPCDeclaration(4, "", "H6s3BB")
"""Query the tile's name and status.

This RPC must be implemented by all tiles and is primarily used to return the
6-character name string that identifies the firmware image running on the
tile. This string is matched against installed proxy classes to find the
appropriate proxy object to use for wrapping the tile.

It can also be used to query the firmware version of the tile or a set of flag
bits about the tile's current state.

Returns:
  - uint16_t: A numerical hardware identifier for the architecture the tile
    is running on.
  - char[6]: The tile firmware's 6-character module identifier that is used to
    match the tile with an appropriate proxy class.
  - uint8_t[3]: The tile's firmware version stored as major, minor, patch.
  - uint8_t: A set of bit flags defining the current state of the tile such as
    whether it is running, trapped in a panic routine, etc.
"""

START_APPLICATION = RPCDeclaration(6, "", "")
"""Inform the peripheral tile that it should pass control to its application firmware.

Once the controller has finished streaming all configuration information to a tile
it sends the tile this RPC so that it can check its configuration state and if
everything is valid pass control to application firmware.
"""
