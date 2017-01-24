import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.auth.env_auth_provider import EnvAuthProvider
import struct
import datetime
import hashlib
import hmac
from copy import deepcopy

def gen_test_data(length):
    data = bytearray([x for x in xrange(0, length)])
    return data

def test_key_finding(monkeypatch):
    """Test to make sure we can find keys stored in environment variables
    """

    uuid = 1
    key1 = '0000000000000000000000000000000000000000000000000000000000000000'

    monkeypatch.setenv('USER_KEY_00000001', key1)
    monkeypatch.setenv('USER_KEY_000000AB', 'abcd')
    monkeypatch.setenv('USER_KEY_000000AC', 'hello world')
    monkeypatch.delenv('USER_KEY_00000002', raising=False)

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
