import struct
import warnings

warnings.warn("unpack was a legacy shim for python < 2.7.5 and will be removed in iotile-core release 5.1.6", DeprecationWarning)

def unpack(fmt, arg):
    """A no-op shim which will be removed in the _next_ release."""
    return struct.unpack(fmt, arg)