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

def test_hmac_rfc_vector():
    """Make sure we correctly reproduce Test Case 2 in rfc4231

    https://tools.ietf.org/html/rfc4231#section-4.2
    """

    auth = BasicAuthProvider()
    data = bytearray("what do ya want for nothing?")
    data2 = bytearray("7768617420646f2079612077616e7420666f72206e6f7468696e673f".decode("hex"))
    assert data == data2

    uuid = 0x6566654a #Little endien encoded uint32_t 'Jefe'

    packed_uuid = struct.pack("<L", uuid)
    assert packed_uuid == 'Jefe'

    known_sig = bytearray("5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843".decode('hex'))

    sig = auth.sign(uuid, 1, data)

    assert hmac.compare_digest(known_sig, sig['signature'])
    assert auth.verify(uuid, 1, data, known_sig)['verified']
