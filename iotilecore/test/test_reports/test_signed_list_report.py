import unittest
import os
import pytest
from iotile.core.exceptions import ExternalError
from iotile.core.hw.reports.signed_list_format import SignedListReport, ReportSignatureFlags
from iotile.core.hw.reports.report import IOTileReading
from iotile.core.hw.auth.env_auth_provider import EnvAuthProvider
from iotile.core.hw.auth.auth_provider import AuthProvider


def make_sequential(iotile_id, stream, num_readings, give_ids=False, root_key=AuthProvider.NoKey, signer=None):
    """Create sequaltial report from reading

    Args:
        iotile_id (int): The uuid of the device that this report came from
        stream (int): The stream that these readings are part of
        num_readings(int): amount of readings
        give_ids(bool): whether to set sequantial id for every reading
        root_key(int): type of root key to sign the report
        signer (AuthProvider): An optional preconfigured AuthProvider that should be used to sign this
            report.  If no AuthProvider is provided, the default ChainedAuthProvider is used.
    """
    readings = []

    for i in range(0, num_readings):
        if give_ids:
            reading = IOTileReading(i, stream, i, reading_id=i+1)
        else:
            reading = IOTileReading(i, stream, i)

        readings.append(reading)

    report = SignedListReport.FromReadings(iotile_id, readings, root_key=root_key, signer=signer)
    return report

def test_basic_parsing():
    """Make sure we can decode a signed report"""

    report = make_sequential(1, 0x1000, 10)
    encoded = report.encode()

    report2 = SignedListReport(encoded)

    assert len(report.visible_readings) == 10
    assert len(report2.visible_readings) == 10

    for i, reading in enumerate(report.visible_readings):
        assert reading == report2.visible_readings[i]

    assert report2.verified is True
    assert report.verified is True
    assert report.signature_flags == ReportSignatureFlags.SIGNED_WITH_HASH

def test_footer_calculation():
    """Test if make_sesuentail set properly ids"""

    report1 = make_sequential(1, 0x1000, 10, give_ids=False)
    report2 = make_sequential(1, 0x1000, 10, give_ids=True)

    assert report1.lowest_id == 0
    assert report1.highest_id == 0

    assert report2.lowest_id == 1
    assert report2.highest_id == 10

def test_userkey_signing(monkeypatch):
    """Make sure we can sign and encrypt reports."""

    monkeypatch.setenv('USER_KEY_00000002', '0000000000000000000000000000000000000000000000000000000000000000')
    signer = EnvAuthProvider()

    with pytest.raises(ExternalError):
        report1 = make_sequential(1, 0x1000, 10, give_ids=True, root_key=AuthProvider.UserKey, signer=signer)

    report1 = make_sequential(2, 0x1000, 10, give_ids=True, root_key=AuthProvider.UserKey, signer=signer)

    encoded = report1.encode()
    report2 = SignedListReport(encoded)

    assert report1.signature_flags == ReportSignatureFlags.SIGNED_WITH_USER_KEY
    assert report2.signature_flags == ReportSignatureFlags.SIGNED_WITH_USER_KEY
    assert report1.verified
    assert report1.encrypted
    assert report2.verified
    assert report2.encrypted

    assert len(report2.visible_readings) == 10

    for i, reading in enumerate(report2.visible_readings):
        assert reading.value == i
        assert reading.reading_id == (i + 1)


def test_str_conversion():
    """Make sure str conversion works."""

    report = make_sequential(1, 0x1000, 10, give_ids=True)

    str_report = str(report)
    assert str_report == 'IOTile Report (length: 204, visible readings: 10, visible events: 0, verified and not encrypted)'
