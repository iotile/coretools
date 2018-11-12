"""Mixin classes that implement specific controller subsystems.

Since the IOTile controller has a lot of different subsystems, it's more
clear to break each one up as a separate mixin class to its easier to
see how each bit of functionality relates.

The specific API and semantics of a controller mixin is as follows:
- The mixin must start in a reset state when it is created.
- The mixin must support a dump() function that serializes its current state
  to a dict.
- The mixin must support a restore(state) function that takes a dict state
  produced by a prior call to dump() and loads it.
- If the mixin needs to reinitialize itself when a controller reset happens
  it needs to implement a clear_to_reset(config_vars) method that gets a
  copy of all of the config variables defined for the tile.  It also needs
  to add itself to the _post_config_subsystems array in the mixin __init__
  function.
"""

from .remote_bridge import RemoteBridgeMixin
from .tile_manager import TileManagerMixin
from .config_database import ConfigDatabaseMixin
from .sensor_log import RawSensorLogMixin
from .sensor_graph import SensorGraphMixin
from .stream_manager import StreamingSubsystemMixin
from .clock_manager import ClockManagerMixin

__all__ = ['RemoteBridgeMixin', 'TileManagerMixin', 'ConfigDatabaseMixin',
           'RawSensorLogMixin', 'SensorGraphMixin', 'StreamingSubsystemMixin',
           'ClockManagerMixin']
