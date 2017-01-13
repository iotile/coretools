import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.auth.basic_auth_provider import BasicAuthProvider
import struct
import datetime
import hashlib
import hmac

def gen_test_data(length):
    data = bytearray([x for x in xrange(0, length)])
    return data

def test_hash_only():
    data = gen_test_data(100)

    auth = BasicAuthProvider()
    sig = auth.sign(0, 0, data)

    digest = sig['signature']

    calced = hashlib.sha256(data).digest()

    assert hmac.compare_digest(calced, digest)

    full = auth.verify(0, 0, data, calced)
    assert full['verified']
    assert full['bit_length'] == 256

    short = auth.verify(0, 0, data, calced[:16])
    assert short['verified']
    assert short['bit_length'] == 128

    none = auth.verify(0, 0, data, bytearray())
    assert not none['verified']

def test_enc_not_supported():
    auth = BasicAuthProvider()

    with pytest.raises(NotFoundError):
        auth.encrypt(0, 0, bytearray())

    with pytest.raises(NotFoundError):
        auth.decrypt(0, 0, bytearray())

def test_methods_not_supported():
    auth = BasicAuthProvider()
    data = gen_test_data(100)

    with pytest.raises(NotFoundError):
        auth.sign(0, 2, data)

    with pytest.raises(NotFoundError):
        auth.sign(0, 1, data)
