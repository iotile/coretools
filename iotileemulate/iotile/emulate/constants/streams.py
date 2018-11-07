"""Globally defined stream names.

These stream declarations document the major system streams that are used
internally in an IOTile device to log important system events.  Each
declaration includes a description of how to interpret the contents of data
logged to that stream.
"""

from iotile.sg import DataStream

def declare_stream(string_name):
    """Create a StreamDeclaration from a string name.

    This will encode the string name into a 16-bit stream
    identifier.

    Args:
        string_name (str): The human-readable name of the stream.

    Returns:
        int: The stream declaration.
"""

    return DataStream.FromString(string_name).encode()


SYSTEM_RESET = declare_stream('system output 1024')
"""Logs a reading every time the IOTile device is reset with SensorGraph running.

This stream records system reboots.  It is only used when there is a
programmed sensor_graph script running in the device.  It can be used for
debugging if a system reboot is unexpected or for keeping track of when the
device's internal uptime is expected to reset back to zero.

The contents of each reading logged in this stream are an oquare integer value
that is architecture specific and describes the technical cause of the reset
(such as power on, brownout, etc).
"""

DATA_CLEARED = declare_stream('system output 1027')
"""Logs a reading every time the sensor log subsystem receives a clear() command.

Each entry in this data stream marks the point in time where the sensor log
was cleared.  It can be used for debugging or forensic purposes if such a
clear was unexpected.  Internally it is used to ensure that there is always a
valid reading inside the senor log to store the current highest allocated
reading id.
"""
