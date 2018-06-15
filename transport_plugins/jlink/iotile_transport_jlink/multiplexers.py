"""Information about known multiplexer  types that we can control over jlink."""
from __future__ import (unicode_literals, print_function, absolute_import)

from typedargs.exceptions import ArgumentError

def _select_ftdi_channel(channel):
    """Select multiplexer channel. Currently uses a FTDI chip via pylibftdi"""
    if channel < 0 or channel > 8:
        raise ArgumentError("FTDI-selected multiplexer only has channels 0-7 valid", channel=channel)
    from pylibftdi import BitBangDevice
    bb = BitBangDevice(auto_detach=False)
    bb.direction = 0x0F
    bb.port = channel
    print("channel %d mux selected" % channel)

KNOWN_MULTIPLEX_FUNCS= {
    'ftdi': _select_ftdi_channel,
}