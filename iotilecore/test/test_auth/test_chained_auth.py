import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.auth.auth_chain import ChainedAuthProvider


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
    auth.sign_report(uuid, ChainedAuthProvider.UserKey, data, report_id=0, sent_timestamp=0)

    #Make sure we throw an error for too short keys
    with pytest.raises(NotFoundError):
        auth.sign_report(0xab, ChainedAuthProvider.UserKey, data, report_id=0, sent_timestamp=0)

    #Make sure we throw an error for keys that aren't hex
    with pytest.raises(NotFoundError):
        auth.sign_report(0xac, ChainedAuthProvider.UserKey, data, report_id=0, sent_timestamp=0)

    #Make sure we throw an error for keys that aren't found
    with pytest.raises(NotFoundError):
        auth.sign_report(2, 1, data, report_id=0, sent_timestamp=0)

    #Make sure we also find the hash only auth module
    auth.sign_report(2, 0, data, report_id=0, sent_timestamp=0)
