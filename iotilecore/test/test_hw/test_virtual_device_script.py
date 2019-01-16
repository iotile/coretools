"""Tests of the virtual_device script."""

import json
from iotile.core.scripts.virtualdev_script import main as virtualdev_main

def save_device_args(tmpdir, filename, data, parent=None):
    """Helper function to dump a config json for use with virtual_device."""

    if parent is not None:
        data = {parent: data}

    path = tmpdir.join(filename)
    path.write(json.dumps(data), mode="w")
    return str(path)


def load_json(local_path):
    with open(str(local_path), "r") as infile:
        return json.load(infile)


def test_basic_virtualdev():
    """Make sure we can invoke virtual_device script."""

    virtualdev_main(['null', 'simple'])


def test_passing_config(tmpdir):
    """Make sure we can pass a --config with device configs."""

    config = save_device_args(tmpdir, 'config.json', parent="device", data={
        'iotile_id': 15
    })

    virtualdev_main(['null', 'realtime_test', '--config', config])


def test_tracking_state(tmpdir):
    """Make sure we can track changes to a device's state."""

    out_state = tmpdir.join('out_state.csv')
    retval = virtualdev_main(['null', 'emulation_demo', '--track', str(out_state)])

    assert retval == 0
    assert out_state.exists()


def test_scenario_loading(tmpdir):
    """Make sure we can load a scenario into a device."""

    scen_file = save_device_args(tmpdir, 'scenario.json', data={
        'name': 'loaded_counter',
        'args': {
            'counter': 15
        },
        'tile': 11
    })

    out_state = tmpdir.join('out_state.json')
    retval = virtualdev_main(['null', 'emulation_demo', '--dump', str(out_state), '--scenario', scen_file])

    assert retval == 0
    assert out_state.isfile()


def test_scenario_loading_list(tmpdir):
    """Make sure we can load a scenario into a device."""

    scen_file = save_device_args(tmpdir, 'scenario.json', data=[{
        'name': 'loaded_counter',
        'args': {
            'counter': 15
        },
        'tile': 11
    }])

    out_state = tmpdir.join('out_state.json')

    retval = virtualdev_main(['null', 'emulation_demo', '--dump', str(out_state), '--scenario', scen_file])
    assert retval == 0
    assert out_state.isfile()
