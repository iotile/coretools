"""Tests for the EmulatedDeviceAdapter class."""

import json
from iotile.core.hw import HardwareManager

def save_device_args(tmpdir, filename, data, parent=None):
    """Helper function to dump a config json."""

    if parent is not None:
        data = {parent: data}

    path = tmpdir.join(filename)
    path.write(json.dumps(data), mode="w")
    return str(path)


def test_basic_functionality():
    """Make sure we can connect to a device."""

    with HardwareManager(port='emulated:emulation_test') as hw:
        results = hw.scan()
        assert len(results) == 1
        assert results[0]['uuid'] == 1

        hw.connect(1)
        _con = hw.controller()
        hw.disconnect()


def test_saving_and_loading_state(tmpdir):
    """Make sure we can save and load state."""

    saved = str(tmpdir.join("state.json"))
    with HardwareManager(port='emulated:emulation_test') as hw:
        hw.connect(1)
        debug = hw.debug()

        debug.save_snapshot(saved)
        debug.load_snapshot(saved)


def test_loading_scenario(tmpdir):
    """Make sure we can load a test scenario."""

    scen_file = save_device_args(tmpdir, 'scenario.json', data=[{
        'name': 'loaded_counters',
        'args': {
            'tracked_counter': 15,
            'manual_counter': 10
        }
    }])

    saved = str(tmpdir.join("state.json"))

    with HardwareManager(port='emulated:emulation_test') as hw:
        hw.connect(1)
        debug = hw.debug()

        debug.open_scenario(scen_file)
        debug.save_snapshot(saved)

    with open(saved, "r") as infile:
        state = json.load(infile)

    assert state['tracked_counter'] == 15
    assert state['manual_counter'] == 10


def test_saving_changes(tmpdir):
    """Make sure we can track and save changes to a device."""

    scen_file = save_device_args(tmpdir, 'scenario.json', data=[{
        'name': 'loaded_counters',
        'args': {
            'tracked_counter': 15,
            'manual_counter': 10
        }
    }])

    change_file = tmpdir.join('out.csv')

    with HardwareManager(port='emulated:emulation_test') as hw:
        hw.connect(1)
        debug = hw.debug()

        debug.track_changes()
        debug.open_scenario(scen_file)
        debug.track_changes(enabled=False)
        debug.save_changes(str(change_file))

    assert change_file.exists()
