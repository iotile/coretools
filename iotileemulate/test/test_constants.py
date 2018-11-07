from iotile.emulate.constants import stream_name, rpc_name


def test_stream_name_formatting():
    """Make sure stream names are formatted correctly."""

    assert stream_name(0x5800 + 1024) == 'SYSTEM_RESET (0x5C00)'
