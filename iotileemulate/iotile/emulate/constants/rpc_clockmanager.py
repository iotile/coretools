"""The clock manager subsystem timestamps data and implements timers.

No other controller subsystem has a concept of device time.  They are all
purely reactive to whatever work items are queued for them.  This is
by design since IOTile devices are meant to be event-driven rather than
polling based whenever possible.

However, there are times when you need to queue operations to be performed
periodically.  It is the clock manager subsystem's job to allow for queuing
these periodic tasks.  Internally, all timers work by just sending a
periodic input to the sensor graph subsystem.  There are 4 timer inputs
available:

- normal tick: generated every 10 seconds in all circumstances.
- fast tick: generated every 1 second when enabled.
- user tick 1: generated at a user configurable interval and easily
  updated dynamically using an RPC.
- user tick 2: generated at a user configurable interval and easily
  updated dynamically using an RPC.

The first two ticks are reserved for internal use and should not be adjusted
by the user, however the last two ticks are designed for easy control in the
field.
"""

from iotile.core.hw.virtual import RPCDeclaration


GET_USER_TIMER = RPCDeclaration(0x2014, "H", "LL")
"""Get the current interval in seconds of a user-controllable timer.

This RPC takes an index identifying the timer that you wish to
query and returns the currently configured interval at which that
timer will present its input to the sensor_graph subsystem.

The interval is always returned in seconds.

There are currently 3 possible timers you can query:
  - 0: The fast timer (which should always be set at 1 second)
  - 1: User timer 1.  This is entirely for application use.
  - 2: User timer 2.  This is entirely for application use.

Args:
  - uint16_t: The timer index.  See above for possible values.

Returns:
  - uint32_t: An error code.
  - uint32_t: The configured timer's current period in seconds.  This
    is only valid if there was no error.

Possible Errors:
  - INVALID_ARRAY_KEY: If the index passed does not name a valid timer.  The
    error will be returned from the SENSOR_GRAPH subsystem.
"""

SET_USER_TIMER = RPCDeclaration(0x2015, "LH", "L")
"""Set the current interval in seconds of a user-controllable timer.

This RPC can set the current time interval of a user controllable timer. The
desired time interval is always passed in seconds and a value of 0 will
disable that timer.  A disabled timer does not present an input to the
sensor_graph subsystem.

**This RPC only affects the value of the timer interval until the next time
the controller resets.**

If you want to make the configured change permanent, you need to couple this
call with setting the appropriate config variable as well.

There are currently 3 possible timers you can query:
  - 0: The fast timer (which should always be set at 1 second)
  - 1: User timer 1.  This is entirely for application use.
  - 2: User timer 2.  This is entirely for application use.

The relevant config variables are:
  - fast timer: 0x2000
  - user timer 1: 0x2002
  - user timer 2: 0x2003

Each config variable is a uint32_t that takes the exact same value you would
pass to SET_USER_TIMER.  It has the effect of calling SET_USER_TIMER with that
value on device reset.

Args:
  - uint32_t: The desired timer interval in seconds.  A value of 0 will disable
    the timer.
  - uint16_t: The index of the timer that you wish to configure.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - INVALID_ARRAY_KEY: If the index passed does not name a valid timer.  The
    error will be returned from the SENSOR_GRAPH subsystem.
"""

GET_CURRENT_TIME = RPCDeclaration(0x1001, "", "L")
"""Get the current UTC or uptime of the device.

If the device has a valid UTC time offset set, it will return an encoded UTC
timestamp encoded as the number of seconds since 1/1/2000 00:00Z with the high
bit set to indicate that it is returning UTC time.

Otherwise this RPC will return the number of seconds since the device last
reset with the MSB clear to prevent misinterpretation as UTC time.

Returns:
  - uint32_t: The current UTC or uptime.
"""

GET_CURRENT_UPTIME = RPCDeclaration(0x100f, "", "L")
"""Get the current uptime of the device.

This RPC will always return  the number of seconds since the device last reset
with the MSB clear to prevent misinterpretation as UTC time, even if a valid
UTC time offset has been set.

Returns:
  - uint32_t: The current UTC or uptime.
"""

GET_UTC_TIME_OFFSET = RPCDeclaration(0x100d, "", "LL")
"""Get the currently programmed UTC time offset.

This RPC returns the current seconds offset that is added to device uptime in
order to produce the value returned by the GET_CURRENT_TIME RPC. Typically,
this value is used to adjust the device's time to UTC.  In that case the
second return value will be a 1 indicating that the device is in valid utc
mode.  Otherwise the second result will be a 0.

Returns:
  - uint32_t: The adjustment value applied to uptime to produce the value
    in GET_CURRENT_TIME_RPC.
  - uint32_t: A 1 if the adjustment is declared to produce valid UTC time.
    Otherwise a 0.
"""

SET_UTC_TIME_OFFSET = RPCDeclaration(0x100e, "LL", "L")
"""Set the currently programmed UTC time offset.

This RPC sets an offset in seconds that will be added to the device's current
uptime and returned whenever the GET_CURRENT_TIME RPC is called. Typically,
this value is used to adjust the device's time to UTC.  In that case the
second argument should be a 1 indicating that the device is in valid utc mode.
Otherwise the second argument should be a 0.  There is no real use case for
setting the second argument to 0 except during testing.

**This offset value is volatile and will not survive a device reset.**

If you want to more permanently synchronize the device's time to UTC,
use the SYNCHRONIZE_CLOCK RPC below.

Args:
  - uint32_t: The offset value in seconds to combine with uptime.
  - uint32_t: A 1 if the adjustment is declared to produce valid UTC time.
    Otherwise a 0.

Returns:
  - uint32_t: An error code.  Currently no errors are possible.
"""

SYNCHRONIZE_CLOCK = RPCDeclaration(0x1010, "L", "L")
"""Persistently synchronize the device's clock to UTC.

This RPC is the same as SET_UTC_TIME_OFFSET RPC except the second flag is
hardcoded to 1, indicating that UTC time is always declared and the value
given is passed to an RTC manager to attempt to persist it in hardware so that
it survives a device reset.  This required hardware realtime clock support,
but if present this RPC will allow persistently synchronizing the device's
clock until the hardware rtc is cleared.

Args:
  - uint32_t: The current UTC time in seconds since 1/1/2000 00:00Z.  This
    will have the device's current uptime subtracted from it in order to
    produce the time offset value passed to SET_UTC_TIME_OFFSET.

Returns:
  - uint32_t: An error code.  Currently no errors are possible.
"""
