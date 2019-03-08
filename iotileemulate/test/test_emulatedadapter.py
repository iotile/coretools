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

    with HardwareManager(port='emulated:emulation_demo@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        results = hw.scan()
        assert len(results) == 1
        assert results[0]['uuid'] == 1

        hw.connect(1)
        hw.get(8, basic=True)
        hw.disconnect()


def test_saving_and_loading_state(tmpdir):
    """Make sure we can save and load state."""

    saved = str(tmpdir.join("state.json"))
    with HardwareManager(port='emulated:emulation_demo@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        hw.connect(1)
        debug = hw.debug()

        debug.save_snapshot(saved)
        debug.load_snapshot(saved)


def test_loading_scenario(tmpdir):
    """Make sure we can load a test scenario."""

    scen_file = save_device_args(tmpdir, 'scenario.json', data=[{
        'name': 'loaded_counter',
        'args': {
            'counter': 15
        },
        'tile': 11
    }])

    saved = str(tmpdir.join("state.json"))

    with HardwareManager(port='emulated:emulation_demo@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        hw.connect(1)
        debug = hw.debug()

        debug.open_scenario(scen_file)
        debug.save_snapshot(saved)

    with open(saved, "r") as infile:
        json.load(infile)


def test_saving_changes(tmpdir):
    """Make sure we can track and save changes to a device."""

    scen_file = save_device_args(tmpdir, 'scenario.json', data=[{
        'name': 'loaded_counter',
        'args': {
            'counter': 15,
        },
        'tile': 11
    }])

    change_file = tmpdir.join('out.csv')

    with HardwareManager(port='emulated:emulation_demo@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        hw.connect(1)
        debug = hw.debug()

        debug.track_changes()
        debug.open_scenario(scen_file)
        debug.track_changes(enabled=False)
        debug.save_changes(str(change_file))

    assert change_file.exists()


def test_async_rpc():
    """Make sure we can send an asynchronous rpc."""

    with HardwareManager(port='emulated:emulation_demo@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        hw.connect(1)

        proxy = hw.get(11, basic=True)

        # This RPC is async
        echo, = proxy.rpc_v2(0x8000, "L", "L", 5)
        assert echo == 5

        # This RPC is sync
        echo, = proxy.rpc_v2(0x8001, "L", "L", 6)
        assert echo == 6


def test_racefree_reset():
    """Make sure we can reset at will."""

    with HardwareManager(port='emulated:emulation_demo@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        hw.connect(1)

        proxy = hw.get(8, basic=True)

        for i in range(0, 10):
            print("starting reset %d" % i)
            proxy.reset(wait=0)
            print("finished reset %d" % i)
