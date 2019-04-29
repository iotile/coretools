"""Helper functions for packing/unpacking msgpack messages."""

import datetime
import msgpack


def unpack(message):
    """Unpack a binary msgpacked message."""

    return msgpack.unpackb(message, raw=False, object_hook=_decode_datetime)


def pack(message):
    """Pack a message into a binary packed message with datetime handling."""

    return msgpack.packb(message, use_bin_type=True, default=_encode_datetime)


def _decode_datetime(obj):
    """Decode a msgpack'ed datetime."""

    if '__datetime__' in obj:
        obj = datetime.datetime.strptime(obj['as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
    return obj


def _encode_datetime(obj):
    """Encode a msgpck'ed datetime."""

    if isinstance(obj, datetime.datetime):
        obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f").encode()}
    return obj
