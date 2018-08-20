"""Test our update script generation and parsing."""

import pytest
from iotile.core.exceptions import ArgumentError, DataError
from iotile.core.hw.update.records import *
from iotile.core.hw import UpdateScript


def test_basic_script_parsing():
    """Make sure we can parse an update script."""

    reflash = ReflashTileRecord(1, bytearray(100), 0x1000)
    unknown = UnknownRecord(128, bytearray(15))

    script = UpdateScript([reflash, unknown])

    encoded = script.encode()

    script2 = UpdateScript.FromBinary(encoded)

    assert len(script2.records) == 2

    with pytest.raises(DataError):
        UpdateScript.FromBinary(encoded, allow_unknown=False)

    assert script == script2
    assert not script != script2

    script3 = UpdateScript([reflash, unknown, unknown])

    assert script3 != script2

def test_set_version():
    """Ensure set_version script performs as intended"""
    app_record = SetDeviceTagRecord(app_tag=12, app_version='3.4')
    os_record = SetDeviceTagRecord(os_tag=56, os_version='7.8')
    both_record = SetDeviceTagRecord(app_tag=56, app_version='7.8', os_tag=12, os_version='3.4')

    script = UpdateScript([app_record, os_record, both_record])
    encoded = script.encode()
    script2 = UpdateScript.FromBinary(encoded)

    assert script2.records[0].update_app == True
    assert script2.records[0].update_os == False
    assert script2.records[0].app_tag == 12
    assert script2.records[0].app_version == '3.4'
    assert script2.records[0].os_tag == None
    assert script2.records[0].os_version == '0.0'

    assert script2.records[1].update_app == False
    assert script2.records[1].update_os == True
    assert script2.records[1].app_tag == None
    assert script2.records[1].app_version == '0.0'
    assert script2.records[1].os_tag == 56
    assert script2.records[1].os_version == '7.8'

    assert script2.records[2].update_app == True
    assert script2.records[2].update_os == True
    assert script2.records[2].app_tag == 56
    assert script2.records[2].app_version == '7.8'
    assert script2.records[2].os_tag == 12
    assert script2.records[2].os_version == '3.4'

    assert str(script2.records[0]) == u'Set device app to (tag:12 version:3.4)'
    assert str(script2.records[1]) == u'Set device os to (tag:56, version:7.8)'
    assert str(script2.records[2]) == u'Set device os to (tag:12, version:3.4) and app to (tag:56, version:7.8)'
