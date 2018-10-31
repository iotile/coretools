"""Tests of various utilities used in IOTileDevice emulation."""

import pytest
from iotile.core.hw.virtual.emulation.emulated_tile import parse_size_name


@pytest.mark.parametrize("type_name, return_tuple", [
    ("uint8_t", (1, 1, 'B', False)),
    ("uint8_t[15]", (15, 1, 'B', True)),
    ("int8_t", (1, 1, 'b', False)),
    ("int8_t[15]", (15, 1, 'b', True)),
    ("char", (1, 1, 'B', False)),
    ("char[15]", (15, 1, 'B', True)),
    ("uint16_t", (2, 2, 'H', False)),
    ("uint16_t[15]", (30, 2, 'H', True)),
    ("int16_t", (2, 2, 'h', False)),
    ("int16_t[15]", (30, 2, 'h', True)),
    ("uint32_t", (4, 4, 'L', False)),
    ("uint32_t[15]", (60, 4, 'L', True)),
    ("int32_t", (4, 4, 'l', False)),
    ("int32_t[15]", (60, 4, 'l', True))
])
def test_config_parsing(type_name, return_tuple):
    """Make sure we can properly parse all config variable types."""

    actual_tuple = parse_size_name(type_name)

    print(type_name)
    assert return_tuple == actual_tuple
