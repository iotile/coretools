"""Tests of the UUID compaction and expansion functions."""

from iotile_transport_blelib.defines import compact_uuid, expand_uuid
from iotile_transport_blelib.iotile import TileBusService


def test_basic_roundtrip():
    """Make sure compacting an expanded uuid is a no-op."""
    start = b'\x01\x02'

    expanded_bytes = expand_uuid(start)
    compressed = compact_uuid(expanded_bytes)
    assert compressed == start

    expanded_int = expand_uuid(uint16=0x0201)
    compressed = compact_uuid(expanded_int)
    assert compressed == start
    assert expanded_int == expanded_bytes


def test_128_bit_noop():
    """Make sure compacting a 128-bit uuid is a noop."""

    assert TileBusService.UUID.bytes_le == compact_uuid(TileBusService.UUID)
