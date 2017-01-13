import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.auth.auth_chain import ChainedAuthProvider
import struct
import datetime
import hashlib
import hmac

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

    auth = ChainedAuthProvider()


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

    #Make sure we also find the hash only auth module
    auth.sign(2, 0, data)