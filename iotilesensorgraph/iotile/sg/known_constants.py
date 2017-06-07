"""Wellknown streams that have global significance for all IOTile devices."""

from .stream import DataStream

# System streams
# These are streams that are generated automatically by an IOTile Device
# according to internal signals and events.  Some indicate abnormal conditions
# and others are standard signals.

# Battery voltage is sampled and reported every 10 seconds
battery_voltage = DataStream.FromString('system input 0')

# The system tick is fired every 10 seconds
system_tick = DataStream.FromString('system input 2')

# The user tick can be configured by the user to any interval
# 1 second or longer.
user_tick = DataStream.FromString('system input 3')

# These streams receive the address of the tile that an external
# user connected to or disconnected from.
user_connected = DataStream.FromString('system input 1025')
user_disconnected = DataStream.FromString('system input 1026')


# Known config variable ids on the controller

## An optional config variable that sets the time interval in seconds
## for the user tick input to sensor graph
config_user_tick_secs = 0x2000
