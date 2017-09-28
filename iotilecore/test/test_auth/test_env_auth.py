"""Test routines inside EnvAuthProvider."""

import pytest
from iotile.core.exceptions import NotFoundError
from iotile.core.hw.auth.env_auth_provider import EnvAuthProvider


def test_key_finding(monkeypatch):
    """Test to make sure we can find keys stored in environment variables."""

    uuid = 1
    key1 = '0000000000000000000000000000000000000000000000000000000000000000'

    monkeypatch.setenv('USER_KEY_00000001', key1)
    monkeypatch.setenv('USER_KEY_000000AB', 'abcd')
    monkeypatch.setenv('USER_KEY_000000AC', 'hello world')
    monkeypatch.delenv('USER_KEY_00000002', raising=False)

    auth = EnvAuthProvider()

    data = bytearray("what do ya want for nothing?")

    #Make sure we can find a key if its defined
    auth.sign_report(uuid, 1, data, report_id=0, sent_timestamp=0)

    #Make sure we throw an error for too short keys
    with pytest.raises(NotFoundError):
        auth.sign_report(0xab, 1, data, report_id=0, sent_timestamp=0)

    #Make sure we throw an error for keys that aren't hex
    with pytest.raises(NotFoundError):
        auth.sign_report(0xac, 1, data, report_id=0, sent_timestamp=0)

    #Make sure we throw an error for keys that aren't found
    with pytest.raises(NotFoundError):
        auth.sign_report(2, 1, data, report_id=0, sent_timestamp=0)


def test_unsupported_methods():
    """Make sure we correctly pass on operations we don't support."""

    auth = EnvAuthProvider()
    data = bytearray("what do ya want for nothing?")

    with pytest.raises(NotFoundError):
        auth.sign_report(1, 0, data, report_id=0, sent_timestamp=0)

    with pytest.raises(NotFoundError):
        auth.sign_report(1, 2, data, report_id=0, sent_timestamp=0)

    with pytest.raises(NotFoundError):
        auth.verify_report(1, 0, data, bytearray(), report_id=0, sent_timestamp=0)

    with pytest.raises(NotFoundError):
        auth.verify_report(1, 2, data, bytearray(), report_id=0, sent_timestamp=0)
