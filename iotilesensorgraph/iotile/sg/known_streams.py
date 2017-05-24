"""Wellknown streams that have global significance for all IOTile devices."""

from .stream import DataStream

# System streams
# These are streams that are generated automatically by an IOTile Device
# according to internal signals and events.  Some indicate abnormal conditions
# and others are standard signals.

# The system tick is fired every 10 seconds
system_tick = DataStream.FromString('system input 2')

# The user tick can be configured by the user to any interval
# 1 second or longer.
user_tick = DataStream.FromString('system input 3')
