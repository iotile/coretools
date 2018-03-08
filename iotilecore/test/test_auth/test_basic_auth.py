from builtins import range
import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.auth.basic_auth_provider import BasicAuthProvider
import hashlib
import hmac


def gen_test_data(length):
    data = bytearray([x for x in range(0, length)])
    return data


def test_hash_only():
    """Verify that hash signatures are calculated correctly."""

    data = gen_test_data(100)

    auth = BasicAuthProvider()
    sig = auth.sign_report(0, BasicAuthProvider.NoKey, data)

    digest = sig['signature']

    calced = hashlib.sha256(data).digest()

    assert hmac.compare_digest(calced, digest)

    full = auth.verify_report(0, BasicAuthProvider.NoKey, data, calced)
    assert full['verified']
    assert full['bit_length'] == 256

    short = auth.verify_report(0, BasicAuthProvider.NoKey, data, calced[:16])
    assert short['verified']
    assert short['bit_length'] == 128

    none = auth.verify_report(0, BasicAuthProvider.NoKey, data, bytearray())
    assert not none['verified']


def test_enc_not_supported():
    """Make sure we don't support encryption with no key."""

    auth = BasicAuthProvider()

    with pytest.raises(NotFoundError):
        auth.encrypt_report(0, BasicAuthProvider.NoKey, bytearray())

    with pytest.raises(NotFoundError):
        auth.decrypt_report(0, BasicAuthProvider.NoKey, bytearray())


def test_methods_not_supported():
    """Make sure we don't support signing with an actualy key."""

    auth = BasicAuthProvider()
    data = gen_test_data(100)

    with pytest.raises(NotFoundError):
        auth.sign_report(0, BasicAuthProvider.UserKey, data)

    with pytest.raises(NotFoundError):
        auth.sign_report(0, BasicAuthProvider.DeviceKey, data)
