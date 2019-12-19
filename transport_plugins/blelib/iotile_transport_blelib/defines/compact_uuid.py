"""Compact UUIDs allowing 2, 4 and 16 byte UUIDs to be represented in compact form."""

import uuid
import binascii
import struct


_BASE = uuid.UUID(hex="{FB349B5F8000-0080-0010-0000-00000000}")


def expand_uuid(bytes_le: bytes = None, uint16: int = None) -> uuid.UUID:
    """Expand a 2, 4 or 16 byte UUID into a full uuid object.

    The Bluetooth specification allow for compacting UUIDs that have a known
    prefix into shorter versions of either 16 or 32 bits based on how much of
    the prefix matches a single global base UUID.
    """

    if bytes_le is None:
        if uint16 is None:
            raise ValueError("One of bytes_le or uint16 must be passed")

        bytes_le = struct.pack("<H", uint16)

    if len(bytes_le) not in (2, 4, 16):
        raise ValueError("Invalid guid length, is not 2, 4 or 16. Data=%s" %
                         binascii.hexlify(bytes_le).decode('utf-8'))

    if len(bytes_le) != 16:
        bytes_le = _BASE.bytes_le[:-len(bytes_le)] + bytes_le

    return uuid.UUID(bytes_le=bytes_le)


def compact_uuid(expanded: uuid.UUID) -> bytes:
    """Represent a 16-byte uuid in its most compacted form.

    This returns either 2, 4 or 16 little endian bytes containing
    the most compact representation of the given UUID.  Bluetooth
    lets you represent UUIds that start with a given global base
    UUID as 2 or 4 byte compact values.  This function checks if
    a UUID is suitable for such a compact representation and
    returns the most compact version of it.

    Return:
        The most compact little-endian bytes representation of the UUID.
    """

    data = expanded.bytes_le
    base = _BASE.bytes_le

    if data[:-2] == base[:-2]:
        return data[-2:]

    if data[:-4] == base[:-4]:
        return data[-4:]

    return data
