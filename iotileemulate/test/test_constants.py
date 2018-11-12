"""Tests of embedded constants and pretty printing."""

from iotile.emulate.constants import stream_name


def test_stream_name_formatting():
    """Make sure stream names are formatted correctly."""

    assert stream_name(0x3800 + 1024) == 'SYSTEM_RESET (0x3C00)'
