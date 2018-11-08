"""Test coverage of the sensorgraph subsystem on the reference controller."""

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
def sg_device():
    """Get a reference device and connected HardwareManager."""

    device = ReferenceDevice({})
    peripheral = EmulatedPeripheralTile(11, b'abcdef', device)
    peripheral.declare_config_variable("test 1", 0x8000, 'uint16_t')
    peripheral.declare_config_variable('test 2', 0x8001, 'uint32_t[5]')

    device.add_tile(11, peripheral)

    adapter = EmulatedDeviceAdapter(None, devices=[device])

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        con = hw.get(8, basic=True)
        sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

        yield sensor_graph, hw


@pytest.fixture(scope="function")
def basic_sg():
    """A preprogrammed basic sensorgraph for testing."""

    device = ReferenceDevice({})
    peripheral = EmulatedPeripheralTile(11, b'abcdef', device)
    peripheral.declare_config_variable("test 1", 0x8000, 'uint16_t')
    peripheral.declare_config_variable('test 2', 0x8001, 'uint32_t[5]')

    device.add_tile(11, peripheral)

    adapter = EmulatedDeviceAdapter(None, devices=[device])

    nodes = [
        "(input 1 always) => counter 1024 using copy_latest_a",
        "(counter 1024 when count >= 1 && constant 1030 when value == 1) => counter 1030 using copy_latest_a"
    ]

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        con = hw.get(8, basic=True)
        sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

        for node in nodes:
            sensor_graph.add_node(node)

        yield sensor_graph, hw


def test_inspect_nodes(sg_device):
    """Ensure that we can inspect the sensor graph nodes that we have programmed."""

    nodes = [
        "(input 1 always) => counter 1024 using copy_latest_a",
        "(counter 1024 when count >= 1 && constant 1030 when value == 1) => counter 1030 using copy_latest_a"
    ]

    sg, hw = sg_device

    for node in nodes:
        sg.add_node(node)

    node1 = sg.inspect_node(0)
    node2 = sg.inspect_node(1)

    assert node1 == nodes[0]
    assert node2 == nodes[1]


def test_persist(basic_sg):
    """Ensure that sensor_graph persists after reset."""

    sg, hw = basic_sg

    sg.persist()
    assert sg.count_nodes() == 2

    hw.get(8, basic=True).reset(wait=0)

    assert sg.count_nodes() == 2
