"""Test coverage of the ReferenceDevice and ReferenceController emulated objects."""

import sys
import pytest
from iotile.core.hw import HardwareManager
from iotile.core.exceptions import HardwareError
from iotile.core.hw.proxy.external_proxy import find_proxy_plugin
from iotile.emulate.virtual import EmulatedPeripheralTile
from iotile.emulate.reference import ReferenceDevice
from iotile.emulate.constants import rpcs, Error
from iotile.emulate.transport import EmulatedDeviceAdapter


@pytest.fixture(scope="function")
def reference():
    """Get a reference device with a controller and single peripheral tile."""

    device = ReferenceDevice({'simulate_time': False})
    peripheral = EmulatedPeripheralTile(10, device)
    device.add_tile(10, peripheral)

    device.start()
    yield device, peripheral
    device.stop()


@pytest.fixture(scope="function")
def reference_hw():
    """Get a reference device and connected HardwareManager."""

    device = ReferenceDevice({'simulate_time': False})
    peripheral = EmulatedPeripheralTile(11, device)
    peripheral.declare_config_variable("test 1", 0x8000, 'uint16_t')
    peripheral.declare_config_variable('test 2', 0x8001, 'uint32_t[5]')

    device.add_tile(11, peripheral)

    adapter = EmulatedDeviceAdapter(None, devices=[device])

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        yield hw, device, peripheral


def test_basic_usage():
    """Make sure we can import and use the objects."""

    with HardwareManager(port='emulated:reference_1_0@#eyJzaW11bGF0ZV90aW1lIjogZmFsc2V9') as hw:
        hw.connect(1)
        debug = hw.debug()

        state = debug.dump_snapshot()
        debug.restore_snapshot(state)


def test_peripheral_tiles():
    """Make sure the controller tile properly brings up the peripheral tiles in a controlled manner."""

    # Don't use the fixture since the purpose of this test is to make sure the fixture works
    device = ReferenceDevice({'simulate_time': False})
    peripheral = EmulatedPeripheralTile(10, device)
    device.add_tile(10, peripheral)

    device.start()
    device.stop()


def test_config_variable_rpcs(reference):
    """Make sure that we can set, list and get config variables."""

    device, peripheral = reference

    peripheral.declare_config_variable("test 1", 0x8000, 'uint16_t')
    peripheral.declare_config_variable('test 2', 0x8001, 'uint32_t[5]')

    # Test listing
    resp = device.simple_rpc(10, rpcs.LIST_CONFIG_VARIABLES, 0)
    count = resp[0]
    ids = resp[1:]

    assert len(ids) == 9
    assert count == 2
    assert ids[:2] == (0x8000, 0x8001)

    # Test describing
    resp1 = device.simple_rpc(10, rpcs.DESCRIBE_CONFIG_VARIABLE, 0x8000)
    resp2 = device.simple_rpc(10, rpcs.DESCRIBE_CONFIG_VARIABLE, 0x8001)
    resp3 = device.simple_rpc(10, rpcs.DESCRIBE_CONFIG_VARIABLE, 0x8002)

    assert len(resp1) == 5
    assert len(resp2) == 5
    assert len(resp3) == 5
    assert resp3[0] == Error.INVALID_ARRAY_KEY

    err, _, _, config_id, packed_size = resp1
    assert err == 0
    assert config_id == 0x8000
    assert packed_size == 2

    err, _, _, config_id, packed_size = resp2
    assert err == 0
    assert config_id == 0x8001
    assert packed_size == (1 << 15) | (5*4)

    # Test setting (make sure to artificially force pre-app started state)
    peripheral.initialized.clear()
    err, = device.simple_rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8000, 0, bytes(bytearray([5, 6])))
    assert err == 0

    err, = device.simple_rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8001, 0, bytes(bytearray([7, 8])))
    assert err == 0

    err, = device.simple_rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8001, 19, bytes(bytearray([7, 8])))
    assert err == Error.INPUT_BUFFER_TOO_LONG

    err, = device.simple_rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8002, 0, bytes(bytearray([7, 8])))
    assert err == Error.INVALID_ARRAY_KEY

    peripheral.initialized.set()
    err, = device.simple_rpc(10, rpcs.SET_CONFIG_VARIABLE, 0x8000, 0, bytes(bytearray([5, 6])))
    assert err == Error.STATE_CHANGE_AT_INVALID_TIME

    # Test Getting
    data, = device.simple_rpc(10, rpcs.GET_CONFIG_VARIABLE, 0x8000, 0)
    assert data == bytearray([5, 6])

    data, = device.simple_rpc(10, rpcs.GET_CONFIG_VARIABLE, 0x8001, 0)
    assert data == bytearray([7, 8])

    data, = device.simple_rpc(10, rpcs.GET_CONFIG_VARIABLE, 0x8002, 0)
    assert data == bytearray([])


def test_snapshot_save_load(reference):
    """Make sure snapshot saving and loading works without error on a peripheral tile."""

    device, _peripheral = reference

    state = device.dump_state()
    device.restore_state(state)


def test_config_database(reference_hw):
    """Test the controller config database RPCs using the canonical proxy plugin."""

    hw, _device, _peripheral = reference_hw

    con = hw.get(8, basic=True)
    slot = hw.get(11, basic=True)
    config_db = find_proxy_plugin('iotile_standard_library/lib_controller', 'ConfigDatabasePlugin')(con)

    # Make sure all of the basic RPCs work
    assert config_db.count_variables() == 0
    config_db.clear_variables()

    # Make sure we can set and get config variables
    config_db.set_variable('slot 1', 0x8000, 'uint16_t', 15)
    config_db.set_variable('slot 1', 0x8001, 'uint32_t[]', "[5, 6, 7]")

    assert config_db.count_variables() == 2
    var8000 = config_db.get_variable(1)
    var8001 = config_db.get_variable(2)

    var8000['metadata'] = str(var8000['metadata'])
    var8001['metadata'] = str(var8001['metadata'])

    assert var8000 == {
        'metadata': 'Target: slot 1\nData Offset: 0\nData Length: 4\nValid: True',
        'name': 0x8000,
        'data': bytearray([15, 0])
    }
    assert var8001 == {
        'metadata': 'Target: slot 1\nData Offset: 4\nData Length: 14\nValid: True',
        'name': 0x8001,
        'data': bytearray([5, 0, 0, 0, 6, 0, 0, 0, 7, 0, 0, 0])
    }

    slot_conf = slot.config_manager()

    # Make sure we stream all variables on a reset
    slot.reset(wait=0)
    assert slot_conf.get_variable(0x8000) == bytearray([15, 0])
    assert slot_conf.get_variable(0x8001) == bytearray([5, 0, 0, 0, 6, 0, 0, 0, 7, 0, 0, 0])

    # Make sure invalidated variables are not streamed and the tile resets them on reset
    config_db.invalidate_variable(1)
    assert config_db.count_variables() == 2
    slot.reset(wait=0)
    assert slot_conf.get_variable(0x8000) == bytearray()
    assert slot_conf.get_variable(0x8001) == bytearray([5, 0, 0, 0, 6, 0, 0, 0, 7, 0, 0, 0])

    # Check memory limits before and after compaction
    usage = config_db.memory_limits()
    assert usage == {
        'data_usage': 18,
        'data_compactable': 4,
        'data_limit': 4096,
        'entry_usage': 2,
        'entry_compactable': 1,
        'entry_limit': 255
    }

    # Make sure we remove invalid and keep valid entries upon compaction
    config_db.compact_database()
    usage = config_db.memory_limits()
    assert usage == {
        'data_usage': 14,
        'data_compactable': 0,
        'data_limit': 4096,
        'entry_usage': 1,
        'entry_compactable': 0,
        'entry_limit': 255
    }

    assert config_db.count_variables() == 1
    slot.reset(wait=0)
    assert slot_conf.get_variable(0x8000) == bytearray()
    assert slot_conf.get_variable(0x8001) == bytearray([5, 0, 0, 0, 6, 0, 0, 0, 7, 0, 0, 0])


def test_tile_manager(reference_hw):
    """Test the controller tile_manager RPCs using the canonical proxy plugin."""

    # Work around inconsistency in output of iotile-support-lib-controller-3 on python 2 and 3
    if sys.version_info.major < 3:
        con_str = 'refcn1, version 1.0.0 at slot 0'
        peri_str = 'noname, version 1.0.0 at slot 1'
    else:
        con_str = "b'refcn1', version 1.0.0 at slot 0"
        peri_str = "b'noname', version 1.0.0 at slot 1"

    hw, _device, _peripheral = reference_hw

    con = hw.get(8, basic=True)
    slot = hw.get(11, basic=True)
    tileman = find_proxy_plugin('iotile_standard_library/lib_controller', 'TileManagerPlugin')(con)

    assert tileman.count_tiles() == 2

    con = tileman.describe_tile(0)
    peri = tileman.describe_tile(1)
    assert str(con) == con_str
    assert str(peri) == peri_str

    # Make sure reseting a tile doesn't add a new entry
    slot.reset(wait=0)

    assert tileman.count_tiles() == 2

    con = tileman.describe_tile(0)
    peri = tileman.describe_tile(1)
    assert str(con) == con_str
    assert str(peri) == peri_str

    con = tileman.describe_selector('controller')
    peri = tileman.describe_selector('slot 1')
    assert str(con) == con_str
    assert str(peri) == peri_str


def test_raw_sensor_log(reference_hw):
    """Test to ensure that the raw sensor log works."""

    hw, _device, _peripheral = reference_hw

    con = hw.get(8, basic=True)
    sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

    assert sensor_graph.count_readings() == {
        'streaming': 0,
        'storage': 0
    }

    assert sensor_graph.highest_id() == 0

    sensor_graph.push_many('output 1', 10, 20)
    sensor_graph.push_many('buffered 1', 15, 25)

    assert sensor_graph.highest_id() == 45

    readings = sensor_graph.download_stream('output 1')
    assert len(readings) == 20

    readings = sensor_graph.download_stream('buffered 1')
    assert len(readings) == 25

    readings = sensor_graph.download_stream('buffered 1', reading_id=44)
    assert len(readings) == 2

    sensor_graph.clear()
    assert sensor_graph.count_readings() == {
        'streaming': 1,
        'storage': 0
    }

    assert sensor_graph.highest_id() == 46


def test_rsl_reset_config(reference_hw):
    """Make sure we properly load config variables into the sensor_log."""

    hw, _device, _peripheral = reference_hw

    import logging
    logger = logging.getLogger(__name__)

    con = hw.get(8, basic=True)
    sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)
    config = find_proxy_plugin('iotile_standard_library/lib_controller', 'ConfigDatabasePlugin')(con)

    config.set_variable('controller', 0x2004, 'uint8_t', 1)

    logger.info("Sending Reset 1")
    con.reset(wait=0)
    logger.info("Done with Reset 1")

    with pytest.raises(HardwareError):
        sensor_graph.push_many('buffered 1', 15, 20000)

    assert sensor_graph.count_readings() == {
        'streaming': 0,
        'storage': 16128
    }

    config.set_variable('controller', 0x2005, 'uint8_t', 1)
    logger.info("Sending Reset 2")
    con.reset(wait=0)

    with pytest.raises(HardwareError):
        sensor_graph.push_many('output 1', 15, 50000)

    assert sensor_graph.count_readings() == {
        'streaming': 48896,
        'storage': 16128
    }


def test_rsl_dump_restore(reference_hw):
    """Make sure the rsl state is properly saved and restored."""

    hw, device, _peripheral = reference_hw
    refcon = device.controller

    con = hw.get(8, basic=True)
    sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

    # Verify that we properly restore data and our download walker
    for i in range(0, 10):
        sensor_graph.push_reading('output 1', i)

    con.rpc(0x20, 0x08, 0x5001, result_format="LLLL")
    err, _timestamp, reading, unique_id, _act_stream = con.rpc(0x20, 0x09, 1, arg_format='B', result_format="LLLLH2x")
    assert err == 0
    assert reading == 0
    assert unique_id == 1

    state = device.dump_state()
    device.restore_state(state)

    # Make sure we keep our same place in the dump stream line
    err, _timestamp, reading, unique_id, _act_stream = con.rpc(0x20, 0x09, 1, arg_format='B', result_format="LLLLH2x")

    assert err == 0
    assert reading == 1
    assert unique_id == 2

    # Make sure we have all of our data
    assert refcon.sensor_log.engine.count() == (0, 10)

    readings = sensor_graph.download_stream('output 1')
    assert len(readings) == 10
    for i, reading in enumerate(readings):
        assert reading.value == i
        assert reading.reading_id == i + 1
