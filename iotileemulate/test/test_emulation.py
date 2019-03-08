"""Tests of various utilities used in IOTileDevice emulation."""

import pytest
from iotile.core.exceptions import DataError, ArgumentError
from iotile.emulate.virtual.emulated_tile import parse_size_name, ConfigDescriptor


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


@pytest.mark.parametrize("type_name, data, python_type, latched_value", [
    ('uint8_t', bytearray([1]), None, 1),
    ('uint8_t', bytearray([255]), None, 255),
    ('int8_t', bytearray([1]), None, 1),
    ('int8_t', bytearray([255]), None, -1),
    ('uint16_t', bytearray([1, 0]), None, 1),
    ('uint16_t', bytearray([255, 255]), None, 0xFFFF),
    ('uint16_t', bytearray([255]), None, 0xFF),  # Make sure size extension happens correctly
    ('int16_t', bytearray([1, 0]), None, 1),
    ('int16_t', bytearray([255, 255]), None, -1),
    ('uint32_t', bytearray([1, 0, 0, 0]), None, 1),
    ('uint32_t', bytearray([255, 255, 255, 255]), None, 0xFFFFFFFF),
    ('int32_t', bytearray([1, 0, 0, 0]), None, 1),
    ('int32_t', bytearray([255, 255, 255, 255]), None, -1),

    # Arrays
    ('uint16_t[5]', bytearray([1, 0, 2, 0, 3, 0, 4, 0]), None, [1, 2, 3, 4]),
    ('uint16_t[5]', bytearray([1, 0, 2, 0, 3, 0, 4]), None, [1, 2, 3, 4]),  # Make sure size extension happens correctly
    ('char[16]', bytearray(b'test string') + bytearray(1), "string", u"test string")
])
def test_config_latching(type_name, data, python_type, latched_value):
    """Make sure we can properly decode variables."""

    print("Testing config latching of type %s with data %s" % (type_name, repr(data)))
    desc = ConfigDescriptor(0x8000, type_name, python_type=python_type)
    desc.update_value(0, data)

    actual_latched = desc.latch()
    assert actual_latched == latched_value


def test_nonnull_string():
    """Make sure we throw an exception for non-null terminated strings."""
    desc = ConfigDescriptor(0x8000, 'char[16]', python_type='string')
    desc.update_value(0, b'test string')

    with pytest.raises(DataError):
        desc.latch()


def test_empty():
    """Make sure we throw en error if we latch an empty config var."""

    desc = ConfigDescriptor(0x8000, 'uint8_t')
    with pytest.raises(DataError):
        desc.latch()


def test_unsupported_type():
    """Make sure we throw en error if we have an unknown python type."""

    with pytest.raises(ArgumentError):
        ConfigDescriptor(0x8000, 'uint8_t', default=b'\0', python_type="unsupported")


@pytest.mark.parametrize("type_name, default_value, latched_value, python_type, expected_exc", [
    ("uint8_t", 15, 15, None, None),
    ("uint8_t[15]", (15, 20, 25), [15, 20, 25], None, None),
    ("uint8_t[15]", bytearray([15, 20, 25]), [15, 20, 25], None, None),
    ("char[16]", u'test', 'test', "string", None),
    ("char[16]", b'test', 'test', "string", None),
    ("char[16]", bytearray(b'test'), 'test', "string", DataError)
])
def test_default_values(type_name, default_value, latched_value, python_type, expected_exc):
    """Make sure we can properly convert default values to binary."""

    desc = ConfigDescriptor(0x8000, type_name, default_value, python_type=python_type)
    desc.clear()

    if expected_exc is not None:
        with pytest.raises(expected_exc):
            desc.latch()
    else:
        assert desc.latch() == latched_value


def test_bool_conversion():
    """Make sure we can convert to bool."""

    desc = ConfigDescriptor(0x8000, 'uint8_t', 0, python_type='bool')
    desc.clear()

    assert desc.latch() is False

    desc = ConfigDescriptor(0x8000, 'uint8_t', 1, python_type='bool')
    desc.clear()

    assert desc.latch() is True

    with pytest.raises(ArgumentError):
        desc = ConfigDescriptor(0x8000, 'uint8_t[2]', 0, python_type='bool')
