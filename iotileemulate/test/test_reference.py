"""Test coverage of the ReferenceDevice and ReferenceController emulated objects."""

import pytest
from iotile.core.hw import HardwareManager
from iotile.emulate.virtual import EmulatedPeripheralTile
from iotile.emulate.reference import ReferenceDevice
from iotile.emulate.constants import rpcs, errors


@pytest.fixture(scope="function")
def reference():
    """Get a reference device with a controller and single peripheral tile."""

    device = ReferenceDevice({})
    peripheral = EmulatedPeripheralTile(10, b'abcdef', device)
    device.add_tile(10, peripheral)

    device.start()
    yield device, peripheral
    device.stop()


def test_basic_usage():
    """Make sure we can import and use the objects."""

    with HardwareManager(port='emulated:reference_1_0') as hw:
        hw.connect(1)
        debug = hw.debug()

        state = debug.dump_snapshot()
        debug.restore_snapshot(state)


def test_peripheral_tiles():
    """Make sure the controller tile properly brings up the peripheral tiles in a controlled manner."""

    # Don't use the fixture since the purpose of this test is to make sure the fixture works
    device = ReferenceDevice({})
    peripheral = EmulatedPeripheralTile(10, b'abcdef', device)
    device.add_tile(10, peripheral)

    device.start()
    device.stop()


def test_config_variable_rpcs(reference):
    """Make sure that we can set, list and get config variables."""

    device, peripheral = reference

    peripheral.declare_config_variable("test 1", 0x8000, 'uint16_t')
    peripheral.declare_config_variable('test 2', 0x8001, 'uint32_t[5]')

    # Test listing
    resp = device.rpc(10, rpcs.LIST_CONFIG_VARIABLES, 0)
    count = resp[0]
    ids = resp[1:]

    assert len(ids) == 9
    assert count == 2
    assert ids[:2] == (0x8000, 0x8001)

    # Test describing
    resp1 = device.rpc(10, rpcs.DESCRIBE_CONFIG_VARIABLE, 0x8000)
    resp2 = device.rpc(10, rpcs.DESCRIBE_CONFIG_VARIABLE, 0x8001)
    resp3 = device.rpc(10, rpcs.DESCRIBE_CONFIG_VARIABLE, 0x8002)

    assert len(resp1) == 5
    assert len(resp2) == 5
    assert len(resp3) == 5
    assert resp3[0] == errors.INVALID_ARRAY_KEY

    err, _, _, config_id, packed_size = resp1
    assert err == 0
    assert config_id == 0x8000
    assert packed_size == 2

    err, _, _, config_id, packed_size = resp2
    assert err == 0
    assert config_id == 0x8001
    assert packed_size == (1 << 15) | (5*4)

    # Test setting (make sure to artificially force pre-app started state)
    peripheral._app_started.clear()
    err, = device.rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8000, 0, bytes(bytearray([5, 6])))
    assert err == 0

    err, = device.rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8001, 0, bytes(bytearray([7, 8])))
    assert err == 0

    err, = device.rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8001, 19, bytes(bytearray([7, 8])))
    assert err == errors.INPUT_BUFFER_TOO_LONG

    err, = device.rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8002, 0, bytes(bytearray([7, 8])))
    assert err == errors.INVALID_ARRAY_KEY

    peripheral._app_started.set()
    err, = device.rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8000, 0, bytes(bytearray([5, 6])))
    assert err == errors.STATE_CHANGE_AT_INVALID_TIME

    # Test Getting
    data, = device.rpc(10, rpcs.GET_CONFIG_VARIABLE, 0x8000, 0)
    assert data == bytearray([5, 6])

    data, = device.rpc(10, rpcs.GET_CONFIG_VARIABLE, 0x8001, 0)
    assert data == bytearray([7, 8])

    data, = device.rpc(10, rpcs.GET_CONFIG_VARIABLE, 0x8002, 0)
    assert data == bytearray([])
