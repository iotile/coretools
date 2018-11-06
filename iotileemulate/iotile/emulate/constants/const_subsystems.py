"""Globally defined subsystem IDs.

All error codes returns from an IOTile device are in either short or long
format.

Short form error codes are 16-bit values that are declared in the errors
module.

Long form error codes have a 16-bit value and a 16-bit subsystem ID.  This
module declares the globally known subsystems.

For both error codes and subsystem IDs, values < 0x8000 are given global
meaning independent of any tile.  Values >= 0x8000 are private to the given
tile that is returning them and must be interpretted in the context of that
tile.
"""

from enum import IntEnum

class ControllerSubsystem(IntEnum):
    """All core subsystems defined for an IOTile controller."""

    TILE_MANAGER = 0x8000
    """The tile management subsystem."""

    PERSISTENT_STORAGE = 0x8001
    """Low level routines dealing with persistent storage."""

    SENSOR_LOG = 0x8002
    """The sensor log subsystem."""

    SENSOR_GRAPH = 0x8003
    """The sensor graph engine subsystem."""

    CONTROLLER = 0x8004
    """Generic controller related routines."""

    REMOTE_BRIDGE = 0x8005
    """The remote bridge subsystem."""

    SECURITY = 0x8006
    """The security subsystem."""
