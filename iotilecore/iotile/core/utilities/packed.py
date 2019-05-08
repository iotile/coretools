import struct
import sys
import warnings

warnings.warn("unpack was a legacy shim for python < 2.7.5 and will be removed in a future iotile-core release", DeprecationWarning)

def unpack(fmt, arg):
    """A shim around struct.unpack to allow it to work on python 2.7.3."""

    if isinstance(arg, bytearray) and not (sys.version_info >= (2, 7, 5)):
        return struct.unpack(fmt, str(arg))

    return struct.unpack(fmt, arg)
