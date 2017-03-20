from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError
import pytest
import os.path
import os


def test_find_virtual_script_nojson():
    """Make sure we can find a virtual device script that's not importable
    """

    path = os.path.join(os.path.dirname(__file__), 'virtual_device.py')
    hw = HardwareManager(port="virtual:%s" % path)


def test_find_virtual_script_withjson():
    """Make sure we can find a script with a json
    """

    path = os.path.join(os.path.dirname(__file__), 'virtual_device.py')
    jsonpath = os.path.join(os.path.dirname(__file__), 'report_test_config_signed.json')

    hw = HardwareManager(port="virtual:%s@%s" % (path, jsonpath))


def test_invalid_virtual_script():
    path = os.path.join(os.path.dirname(__file__), 'unknown_virtual_device.py')

    with pytest.raises(ArgumentError):
        hw = HardwareManager(port="virtual:%s" % path)


def test_find_virtual_script_unknownjson():
    """Make sure we can find a script with a json
    """

    path = os.path.join(os.path.dirname(__file__), 'virtual_device.py')
    jsonpath = os.path.join(os.path.dirname(__file__), 'unknown_json_config.json')

    with pytest.raises(ArgumentError):
        hw = HardwareManager(port="virtual:%s@%s" % (path, jsonpath))
