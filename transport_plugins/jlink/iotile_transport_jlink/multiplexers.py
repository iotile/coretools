"""Information about known multiplexer  types that we can control over jlink."""

from typedargs.exceptions import ArgumentError

def _select_ftdi_channel(channel):
    """Select multiplexer channel. Currently uses a FTDI chip via pylibftdi"""
    if channel < 0 or channel > 8:
        raise ArgumentError("FTDI-selected multiplexer only has channels 0-7 valid, "
                            "make sure you specify channel with -c channel=number", channel=channel)
    from pylibftdi import BitBangDevice
    bb = BitBangDevice(auto_detach=False)
    bb.direction = 0b111
    bb.port = channel

KNOWN_MULTIPLEX_FUNCS= {
    'ftdi': _select_ftdi_channel,
}
