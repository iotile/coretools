"""Helpful shared utility functions."""

import datetime
import struct
from typing import Union, TYPE_CHECKING
from typedargs.exceptions import ArgumentError, NotFoundError

try:
    if TYPE_CHECKING:
        from Crypto.Cipher._mode_ecb import EcbMode

    from Crypto.Cipher import AES
except ImportError as err:
    AES = None  # type:ignore


_Y2K_NAIVE = datetime.datetime(2000, 1, 1)
_Y2K_AWARE = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)
_MAX_TIMESTAMP = (1 << 31) - 1

def timestamp_to_integer(timestamp) -> int:
    """Safely convert a datetime or integer to an iotile compatible encoded time.

    The encoding is that an integer number of seconds is stored in a uint32
    and is interpreted in one of two ways depending on whether the high bit is set.

    - If the high bit (1 << 31) is set then the value should be interpreted as
      the number of seconds since 1/1/2000 in UTC.  So it is a utc timestamp
      with a different, more recent epoch.

    - Otherwise, the value be interpreted as the number of
      seconds since the device rebooted.  This uptime cannot be directly
      converted to UTC time unless the observer has access to a valid utc
      clock and can associate a specific uptime value to UTC time to establish
      an offset.
    """

    if isinstance(timestamp, int):
        return timestamp

    if not isinstance(timestamp, datetime.datetime):
        raise ArgumentError("Unknown timelike object that is not an int or datetime: %r" % timestamp)

    if timestamp.tzinfo is None:
        delta = (timestamp - _Y2K_NAIVE).total_seconds()
    else:
        delta = (timestamp - _Y2K_AWARE).total_seconds()

    # We only have 31 bits of range to pack this timestamp since we set the high bit to indicate UTC
    if delta < 0:
        raise ArgumentError("Cannot represent times before 1/1/2000, received: %s" % timestamp)
    if delta > _MAX_TIMESTAMP:
        raise ArgumentError("Timestamp too far in the future, received: %s" % timestamp)

    return (1 << 31) | int(delta)


def generate_nonce(iotile_id: int, timestamp: int, reboot_count: int, channel_and_counter: int) -> bytes:
    """Build the proper nonce value for v2 advertisement encryption.

    This is an internal function that serves as a reference implementation of
    the nonce format for encrypting and decrypting v2 ble advertisements.
    Since this is an internal function, no validation is performed on the
    arguments.  If they are out of range, struct.error exceptions will be
    raised directly.
    """

    nonce = struct.pack("<LLHBBx", iotile_id, timestamp, reboot_count & 0xFFFF, reboot_count >> 16,
                        channel_and_counter)
    return nonce


def generate_rotated_key(key_or_cipher: Union[bytes, 'EcbMode'], timestamp: int, mask_bits: int = 6):
    """Generate a short-lived key for encrypting a v2 advertisement."""

    if isinstance(key_or_cipher, bytes):
        if AES is None:
            raise NotFoundError("Missing pycryptodome dependency, cannot generate rotated key") from err

        cipher = AES.new(key_or_cipher, AES.MODE_ECB)
    else:
        cipher = key_or_cipher

    mask = (1 << mask_bits) - 1
    masked_timestamp = timestamp & (~mask)

    message = struct.pack("<L12x", masked_timestamp)
    rotated_key = cipher.encrypt(message)

    return rotated_key


def encrypt_v2_packet(message: bytes, key: bytes, nonce: bytes):
    """Lowlevel internal routine to perform AES-CCM packet encryption.

    This function expects to be called with a 31 byte v2 advertisement packet
    and it returns the correct encrypted version of that same packet according
    to the given key and nonce.  Note that the key and nonce are themselves
    derived partially from the contents of the packet.  For clarify, this
    method expects them to be provided as is and does not attempt to calculate
    them since the source keying material could come from many different
    sources.
    """

    if AES is None:
        raise NotFoundError("Missing pycryptodome dependency, cannot encrypt data") from err

    if len(key) != 16:
        raise ArgumentError("Invalid encryption key that should be 128 bits long, was %d bytes" % len(key))

    if len(nonce) != 16:
        raise ArgumentError("Invalid AES CCM nonce that should be 16 bytes long, was %d bytes" % len(nonce))

    if len(message) != 31:
        raise ArgumentError("Invalid v2 packet data with incorrect length, expected=31, found=%d" % len(message))

    header = message[:7]
    aad = message[7:21]
    body = message[21:27]
    #_original_tag = message[27:31]

    cipher = AES.new(key, AES.MODE_CCM, nonce, mac_len=4)

    # Ignoring mypy errors since it misidentifies what options are supported by this cipher mode
    cipher.update(aad)  # type: ignore
    encrypted, tag = cipher.encrypt_and_digest(body)  # type: ignore

    encrypted_packet = header + aad + encrypted + tag
    return encrypted_packet
