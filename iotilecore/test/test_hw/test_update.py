"""Test our update script generation and parsing."""

import pytest
from iotile.core.exceptions import ArgumentError, DataError
from iotile.core.hw.update.records import *
from iotile.core.hw import UpdateScript


def test_basic_script_parsing():
    """Make sure we can parse an update script."""

    reflash = ReflashTileRecord(1, bytearray(100), 0x1000)
    unknown = UnknownRecord(128, bytearray(15))

    script = UpdateScript([reflash, unknown])

    encoded = script.encode()

    script2 = UpdateScript.FromBinary(encoded)

    assert len(script2.records) == 2

    with pytest.raises(DataError):
        UpdateScript.FromBinary(encoded, allow_unknown=False)

    assert script == script2
    assert not script != script2

    script3 = UpdateScript([reflash, unknown, unknown])

    assert script3 != script2
