import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.auth.env_auth_provider import EnvAuthProvider
import struct
import datetime
import hashlib
import hmac

def gen_test_data(length):
    data = bytearray([x for x in xrange(0, length)])
    return data

def test_key_finding():
    """Test to make sure we can find keys stored in environment variables
    """

    uuid = 1
    key1 = '0000000000000000000000000000000000000000000000000000000000000000'
    os.environ['USER_KEY_00000001'] = key1
    os.environ['USER_KEY_000000AB'] = 'abcd'
    os.environ['USER_KEY_000000AC'] = 'hello world'

    #Make sure there's no key 2
    if 'USER_KEY_00000002' is os.environ:
        del os.environ['USER_KEY_00000002']

    auth = EnvAuthProvider()

    data = bytearray("what do ya want for nothing?")

    #Make sure we can find a key if its defined
    auth.sign(uuid, 1, data)

    #Make sure we throw an error for too short keys
    with pytest.raises(NotFoundError):
        auth.sign(0xab, 1, data)

    #Make sure we throw an error for keys that aren't hex
    with pytest.raises(NotFoundError):
        auth.sign(0xac, 1, data)

    #Make sure we throw an error for keys that aren't found
    with pytest.raises(NotFoundError):
        auth.sign(2, 1, data)

def test_hmac_rfc_vector():
    """Make sure we correctly reproduce test cases in rfc4231

    https://tools.ietf.org/html/rfc4231#section-4.2
    """

    #Test Case 2
    auth = EnvAuthProvider()
    data = bytearray("what do ya want for nothing?")
    data2 = bytearray("7768617420646f2079612077616e7420666f72206e6f7468696e673f".decode("hex"))
    assert data == data2

    os.environ['USER_KEY_6566654A'] = '4a65666500000000000000000000000000000000000000000000000000000000'
    uuid = 0x6566654a #Little endien encoded uint32_t 'Jefe'

    known_sig = bytearray("5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843".decode('hex'))

    sig = auth.sign(uuid, 1, data)

    assert hmac.compare_digest(known_sig, sig['signature'])
    assert auth.verify(uuid, 1, data, known_sig)['verified']

def test_unsupported_methods():
    auth = EnvAuthProvider()
    data = bytearray("what do ya want for nothing?")

    with pytest.raises(NotFoundError):
        auth.sign(1, 0, data)

    with pytest.raises(NotFoundError):
        auth.sign(1, 2, data)

    with pytest.raises(NotFoundError):
        auth.verify(1, 0, data, bytearray())

    with pytest.raises(NotFoundError):
        auth.verify(1, 2, data, bytearray())

    with pytest.raises(NotFoundError):
        auth.encrypt(1, 1, data)

    with pytest.raises(NotFoundError):
        auth.decrypt(1, 1, data)
