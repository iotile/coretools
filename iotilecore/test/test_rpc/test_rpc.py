import pytest
import struct
import json
import os.path
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.hw.exceptions import RPCNotFoundError
from typedargs.exceptions import KeyValueException
from iotile.core.hw.virtual import VirtualTile, RPCInvalidArgumentsError

@pytest.fixture
def registry():
    reg = ComponentRegistry()
    reg.clear()
    reg.clear_components()
    path = os.path.join(os.path.dirname(__file__), 'rpc_proxy.py')
    reg.register_extension('iotile.proxy', 'virtual_tile', path)

    yield reg

@pytest.fixture
def p(tmpdir):

    path = os.path.join(os.path.dirname(__file__), 'rpc_device.py')
    config = {
        "device":
            {
                "tiles":
                    [
                        {
                            "address": 10,
                            "name": path,
                            "args": {}
                        }
                    ],
                "iotile_id": 1
            }
    }

    config_path_obj = tmpdir.join('tasks.json')
    config_path_obj.write(json.dumps(config))

    config_path = str(config_path_obj)

    hw = HardwareManager(port='virtual:tile_based@%s' % config_path)
    hw.connect_direct(1)
    tile = hw.get(10)
    yield tile
    hw.disconnect()


def test_add_rpc(registry, p):
    res1 = p.test_add_v1(1, 2)
    assert res1 == 3
    res2 = p.test_add_v2(1, 2)
    assert res2 == 3


def test_null_rpc(registry, p):
    p.test_null_v1()
    p.test_null_v2()


def test_invalid_rpc_args_length(registry, p):
    with pytest.raises(RPCInvalidArgumentsError) as e:
        p.test_invalid_arg_length_rpc_v2()
    assert e.type == RPCInvalidArgumentsError

    # This doesn't fail because we don't validate arg length on rpc_v1
    p.test_invalid_arg_length_rpc_v1()


def test_invalid_rpc_args(registry, p):
    with pytest.raises(RPCInvalidArgumentsError) as e:
        p.test_invalid_args_missing_rpc_v2()
    assert e.type == RPCInvalidArgumentsError

    with pytest.raises(struct.error) as e:
        p.test_invalid_args_missing_rpc_v1()
    assert e.type == struct.error


def test_rpc_does_not_exist(registry, p):
    with pytest.raises(RPCNotFoundError) as e:
        p.test_rpc_does_not_exist_v1()
    assert e.type == RPCNotFoundError

    with pytest.raises(RPCNotFoundError) as e:
        p.test_rpc_does_not_exist_v2()
    assert e.type == RPCNotFoundError
