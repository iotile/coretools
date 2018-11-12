"""Tests of the clock manager subsystem."""

import pytest

from iotile.core.hw import HardwareManager
from iotile.core.exceptions import HardwareError
from iotile.core.hw.proxy.external_proxy import find_proxy_plugin
from iotile.emulate.reference import ReferenceDevice
from iotile.emulate.transport import EmulatedDeviceAdapter


@pytest.fixture(scope="function")
def basic_device():
    """A preprogrammed basic sensorgraph for testing."""

    device = ReferenceDevice({})
    adapter = EmulatedDeviceAdapter(None, devices=[device])

    nodes = [
        "(input 1 always) => counter 1024 using copy_latest_a",
        "(counter 1024 when count >= 1 && constant 1030 when value == 1) => counter 1030 using copy_latest_a",
        "(counter 1030 when count >= 4) => output 1 using copy_all_a"
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

