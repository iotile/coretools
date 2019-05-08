"""RPCs implemented by the TileManager subsystem on an IOTile controller.

These RPCs allow querying information on any registered tiles (including the
controller itself which lists itself first).  The TileManager subsystem is
also involved in bootloading new firmware onto peripheral tiles so there are
RPCs for tiles that are instructed to bootload as a result of their call to
REGISTER_TILE to use to notify the controller of their bootloading status and
request new chunks of firmware.
"""

from iotile.core.hw.virtual import RPCDeclaration


REGISTER_TILE = RPCDeclaration(0x2a00, "3B6s6BBL", "HHH")
"""Register a peripheral tile with the local controller.

This RPC is called by all peripheral tiles when they first boot up in order to
check in with the IOTile controller on their local bus.  The tiles send
information about themselves that the controller caches in its tile_manager
subsystem.

Args:
  - uint8_t: a numerical hardware type identifer for the processor the tile is
    running on.
  - two bytes: (major, minor) API level of the tile executive running on this
    tile.  The api version is encoded with the major version as a byte
    followed by the minor version.
  - 6-character string: The tile firmware identifier that is used to match
    it with the correct proxy module by HardwareManager.
  - 3 bytes: (major, minor, patch) version identifier of the application
    firmware running on this tile.
  - 3 bytes: (major, minor, patch) version identifier of the tile executive
    running on this tile.
  - uint8_t: The slot number that refers to the physical location of this
    tile on the board.  It is used to assign the tile a fixed address on
    the TileBus.
  - uint32_t: A unique identifier for this tile, if the tile supports
    unique identifiers.

Returns:
  - uint16_t: The address that the tile was assigned based on the slot informatioN
    that it passed to the controller.
  - uint16_t: The run-level for the tile.  The tile executive uses this information
    to determine whether it should pass control to application firmware or prevent
    any user application code from running because the device is in safe mode.
  - uint16_t: Whether the tile should run in debug mode.  This hint tells the
    tile firmware that it should ensure that it runs in a debug-compatible
    mode, which may among other things entail using lighter sleep states that
    don't break attached debuggers.
"""

COUNT_TILES = RPCDeclaration(0x2a01, "", "H")
"""Count how many tiles have registered themselves with the controller.

This RPC is implemented by IOTile controllers and forms part of the
TileManager subsystem.  It is used to allow iteration over the TileManager's
cache of tile registration data by listing how many tiles are in the cache.

The count of registered tiles can never decrease unless the controller resets
since there is no UNREGISTER_TILE command.

Returns:
 - uint16_t: The number of currently registered tiles.
"""

DESCRIBE_TILE = RPCDeclaration(0x2a02, "H", "3B6s6BBL")
"""Describes the tile at the given index in the TileManager cache.

The information returned is the exact same data as what REGISTER_TILE
includes as its argument.

Args:
  - uint16_t: The index of the tile you wish to describe.  Must be less than
    what COUNT_TILES returns.

Returns:
  - uint8_t: a numerical hardware type identifer for the processor the tile is
    running on.
  - two bytes: (major, minor) API level of the tile executive running on this
    tile.  The api version is encoded with the major version as a byte
    followed by the minor version.
  - 6-character string: The tile firmware identifier that is used to match it
    with the correct proxy module by HardwareManager.
  - 3 bytes: (major, minor, patch) version identifier of the application
    firmware running on this tile.
  - 3 bytes: (major, minor, patch) version identifier of the tile executive
    running on this tile.
  - uint8_t: The slot number that refers to the physical location of this tile
    on the board.  It is used to assign the tile a fixed address on the
    TileBus.
  - uint32_t: A unique identifier for this tile, if the tile supports unique
    identifiers.
"""

GET_TILE_STATE = RPCDeclaration(0x2a03, "H", "BB")
"""Get the current address and state of a tile by index.

This RPC queries the TileManager cache for the assigned address and
state of the tile at the given index.

Args:
  - uint16_t: The index of the tile you wish to describe.  Must be less than
    what COUNT_TILES returns.

Returns:
  - uint8_t: The address that the tile was assigned.
  - uint8_t: The tile's state, which is taken from the TILE_STATE enum to
    indicate if it is running, dormant, registered, bootloading, etc.
"""

BOOTLOAD_NOTIFY_STARTED = RPCDeclaration(0x2a04, "", "")
"""Notify the controller that the sender has started bootloading.

Only a single tile is allowed to bootload at a time so no parameters are sent
indicating which tile has started bootloading.  TileManager maintains internal
state indicating which tile, if any, is supposed to bootload.

If no tile is supposed to bootload, the RPC fails with the UNKNOWN error code.
"""

BOOTLOAD_POLL_FIRMWARE = RPCDeclaration(0x2a05, "", "")
"""Request a chunk of firmware starting at a specific address from the controller.

Tiles that are in bootloading mode must repeatedly call this function to read in
their new firmware image chunk by chunk, incrementing address with each call.

It is not required that the tile's read their firmware chunks in order.

Args:
  - uint32_t: The address of the firmware chunk that you wish to receive.

Returns:
  - char[]: Up to 20 bytes of firmware starting at the given address.  May be
    less if the firmware image ends less than 20 bytes after the given
    address.
"""

BOOTLOAD_NOTIFY_ENDED = RPCDeclaration(0x2a06, "", "")
"""Notify the controller that the sender has finished bootloading.

Only a single tile is allowed to bootload at a time so no parameters are sent
indicating which tile has started bootloading.  TileManager maintains internal
state indicating which tile, if any, is supposed to bootload.

If no tile is supposed to bootload, the RPC fails with the UNKNOWN error code.
"""
