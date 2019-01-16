"""Tests of the clock manager subsystem."""

import datetime
import pytest

from iotile.core.hw import HardwareManager
from iotile.core.exceptions import HardwareError
from iotile.core.hw.proxy.external_proxy import find_proxy_plugin
from iotile.emulate.reference import ReferenceDevice
from iotile.emulate.transport import EmulatedDeviceAdapter


@pytest.fixture(scope="function")
def basic_device():
    """A preprogrammed basic sensorgraph for testing."""

    device = ReferenceDevice({'simulate_time': False})
    adapter = EmulatedDeviceAdapter(None, devices=[device])

    nodes = [
        "(system input 2 always) => output 1 using copy_latest_a",
        "(system input 3 always) => output 2 using copy_latest_a",
        "(system input 5 always) => output 3 using copy_latest_a",
        "(system input 6 always) => output 4 using copy_latest_a"
    ]

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        con = hw.get(8, basic=True)
        sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

        for node in nodes:
            sensor_graph.add_node(node)

        sensor_graph.add_streamer('output 10', 'controller', True, 'individual', 'telegram')

        yield hw, device


def test_user_ticks(basic_device):
    """Make sure that we can control user ticks."""

    hw, device = basic_device

    con = hw.get(8, basic=True)
    sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)
    config = find_proxy_plugin('iotile_standard_library/lib_controller', 'ConfigDatabasePlugin')(con)

    assert sensor_graph.user_tick(0) == 0
    assert sensor_graph.user_tick(1) == 0
    assert sensor_graph.user_tick(2) == 0

    with pytest.raises(HardwareError):
        sensor_graph.user_tick(3)

    sensor_graph.set_user_tick(0, 1)
    sensor_graph.set_user_tick(1, 5)
    sensor_graph.set_user_tick(2, 6)

    with pytest.raises(HardwareError):
        sensor_graph.set_user_tick(3, 1)

    assert sensor_graph.user_tick(0) == 1
    assert sensor_graph.user_tick(1) == 5
    assert sensor_graph.user_tick(2) == 6

    # Make sure set on reset works
    config.set_variable('controller', 0x2000, 'uint32_t', 2)
    config.set_variable('controller', 0x2002, 'uint32_t', 4)
    config.set_variable('controller', 0x2003, 'uint32_t', 7)

    con.reset(wait=0)
    device.wait_idle()

    assert sensor_graph.user_tick(0) == 2
    assert sensor_graph.user_tick(1) == 4
    assert sensor_graph.user_tick(2) == 7


def test_tick_inputs(basic_device):
    """Test to make sure that ticks are sent to sensor_graph."""

    hw, device = basic_device

    con = hw.get(8, basic=True)
    sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)
    clock_man = device.controller.clock_manager

    sensor_graph.enable()

    assert clock_man.uptime == 0

    sensor_graph.set_user_tick(0, 1)
    sensor_graph.set_user_tick(1, 2)
    sensor_graph.set_user_tick(2, 5)

    for i in range(1, 11):
        device.controller.clock_manager.handle_tick()
        assert clock_man.uptime == i

    dump1 = sensor_graph.download_stream('output 1')
    assert len(dump1) == 1
    key_parts_1 = [(x.raw_time, x.value) for x in dump1]
    assert key_parts_1 == [(10, 10)]

    dump2 = sensor_graph.download_stream('output 2')
    assert len(dump2) == 10
    key_parts_2 = [(x.raw_time, x.value) for x in dump2]
    assert key_parts_2 == list(zip(range(1, 11), range(1, 11)))

    dump3 = sensor_graph.download_stream('output 3')
    assert len(dump3) == 5
    key_parts_3 = [(x.raw_time, x.value) for x in dump3]
    assert key_parts_3 == list(zip(range(2, 11, 2), range(2, 11, 2)))

    dump4 = sensor_graph.download_stream('output 4')
    assert len(dump4) == 2
    key_parts_4 = [(x.raw_time, x.value) for x in dump4]
    assert key_parts_4 == list(zip(range(5, 11, 5), range(5, 11, 5)))


def test_utc_time(basic_device):
    """Make sure we can get and set utc time."""

    hw, device = basic_device

    con = hw.get(8, basic=True)
    test_interface = find_proxy_plugin('iotile_standard_library/lib_controller', 'ControllerTestPlugin')(con)

    test_time = datetime.datetime(2018, 11, 11, 16, 0, 0)
    zero = datetime.datetime(1970, 1, 1)
    y2k_zero = datetime.datetime(2000, 1, 1)

    device.controller.clock_manager.handle_tick()

    delta = (test_time - zero).total_seconds()
    y2k_delta = (test_time - y2k_zero).total_seconds()

    test_interface.synchronize_clock(delta)
    device_time = test_interface.current_time()
    device_uptime = test_interface.get_uptime()
    info = test_interface.get_timeoffset()

    assert device_time & (1 << 31)
    assert (device_time & ~(1 << 31)) == int(y2k_delta)
    assert device_uptime == 1
    assert info == {'is_utc': True, 'offset': int(y2k_delta) - 1}
