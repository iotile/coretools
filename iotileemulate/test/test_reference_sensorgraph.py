"""Test coverage of the sensorgraph subsystem on the reference controller."""

import sys
import pytest
import time
from iotile.core.hw import HardwareManager
from iotile.core.hw.reports import SignedListReport
from iotile.core.exceptions import HardwareError
from iotile.core.hw.proxy.external_proxy import find_proxy_plugin
from iotile.emulate.virtual import EmulatedPeripheralTile
from iotile.emulate.reference import ReferenceDevice
from iotile.emulate.demo import DemoEmulatedDevice
from iotile.emulate.constants import rpcs, Error
from iotile.emulate.transport import EmulatedDeviceAdapter

@pytest.fixture(scope="function")
def sg_device():
    """Get a reference device and connected HardwareManager."""

    device = ReferenceDevice({'simulate_time': False})
    peripheral = EmulatedPeripheralTile(11, device)
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

    device = ReferenceDevice({'simulate_time': False})
    peripheral = EmulatedPeripheralTile(11, device)
    peripheral.declare_config_variable("test 1", 0x8000, 'uint16_t')
    peripheral.declare_config_variable('test 2', 0x8001, 'uint32_t[5]')

    device.add_tile(11, peripheral)

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

        yield sensor_graph, hw, device


@pytest.fixture(scope="function")
def streaming_sg():
    """A preprogrammed basic sensorgraph for testing streaming."""

    device = ReferenceDevice({'simulate_time': False})

    adapter = EmulatedDeviceAdapter(None, devices=[device])

    nodes = [
        "(input 1 when count >= 1) => output 1 using copy_latest_a",
        "(input 2 when count >= 1) => output 2 using copy_latest_a",
        "(input 3 when count >= 1 && constant 1 always) => unbuffered 1 using trigger_streamer"
    ]

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        con = hw.get(8, basic=True)
        sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

        for node in nodes:
            sensor_graph.add_node(node)

        sensor_graph.push_reading('constant 1', 0)

        sensor_graph.add_streamer('output 1', 'controller', False, 'individual', 'telegram')
        sensor_graph.add_streamer('output 2', 'controller', False, 'hashedlist', 'telegram', withother=0)

        yield sensor_graph, hw, device


@pytest.fixture(scope="function")
def empty_sg():
    """An empty sensorgraph for testing."""

    device = ReferenceDevice({'simulate_time': False})

    adapter = EmulatedDeviceAdapter(None, devices=[device])

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        con = hw.get(8, basic=True)
        sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)
        yield sensor_graph, hw, device


@pytest.fixture(scope="function")
def rpc_sg():
    """A basic sg for testing the rpc executor."""

    device = DemoEmulatedDevice({'simulate_time': False})

    adapter = EmulatedDeviceAdapter(None, devices=[device])

    nodes = [
        "(input 1 always) => unbuffered 1024 using copy_latest_a",
        "(unbuffered 1024 when count == 1 && constant 1024 always) => output 1 using call_rpc"
    ]

    with HardwareManager(adapter=adapter) as hw:
        hw.connect(1)

        con = hw.get(8, basic=True)
        sensor_graph = find_proxy_plugin('iotile_standard_library/lib_controller', 'SensorGraphPlugin')(con)

        for node in nodes:
            sensor_graph.add_node(node)

        sensor_graph.push_reading('constant 1024', 753666)

        yield sensor_graph, hw, device


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


def test_inspect_streamers(basic_sg):
    """Ensure that we can add and inspect streamers."""

    sg, _hw, _device = basic_sg
    assert str(sg.inspect_streamer(0)) == 'realtime streamer on output 10'


def test_persist(basic_sg):
    """Ensure that sensor_graph persists after reset."""

    sg, hw, _device = basic_sg

    sg.persist()
    assert sg.count_nodes() == 3
    assert str(sg.inspect_streamer(0)) == 'realtime streamer on output 10'

    hw.get(8, basic=True).reset(wait=0)

    # Make sure we recover both streamers and nodes
    assert sg.count_nodes() == 3
    assert str(sg.inspect_streamer(0)) == 'realtime streamer on output 10'


def test_graph_input(basic_sg):
    """Ensure that graph_input works."""

    sg, hw, device = basic_sg
    sg.enable()

    sg.push_reading('constant 1030', 1)
    sg.input('input 1', 1)

    device.wait_idle()

    assert sg.inspect_virtualstream('input 1') == 1
    assert sg.inspect_virtualstream('counter 1024') == 1
    assert sg.count_stream('output 1') == 0

    sg.input('input 1', 2)
    device.wait_idle()
    assert sg.count_stream('output 1') == 0
    sg.input('input 1', 3)
    device.wait_idle()
    assert sg.count_stream('output 1') == 0
    sg.input('input 1', 4)
    device.wait_idle()

    values = sg.download_stream('output 1')
    assert [x.value for x in values] == [4, 4, 4, 4]


def test_streaming(streaming_sg):
    """Ensure that streamers work."""

    sg, hw, _device = streaming_sg
    sg.enable()

    hw.enable_streaming()
    sg.input('input 1', 0)
    sg.input('input 1', 1)
    sg.input('input 1', 2)
    sg.input('input 2', 5)
    sg.input('input 2', 6)
    sg.input('input 2', 7)
    sg.input('input 2', 8)
    sg.input('input 3', 3)

    reports = hw.wait_reports(4, timeout=0.5)
    assert len(reports) == 4
    for i, report in enumerate(reports[:-1]):
        assert report.visible_readings[0].value == i

    signed = reports[-1]
    assert isinstance(signed, SignedListReport)
    readings = signed.visible_readings
    assert len(readings) == 4

    for i, reading in enumerate(readings):
        assert reading.value == 5 + i
        assert reading.reading_id == 5 + i


def test_streaming_multiple_times(empty_sg):
    """Verify that we can send multiple reports from the same streamer.

    Verifies Issue #700.
    """

    sg, hw, _device = empty_sg

    sg.add_streamer('input 1', 'controller', True, 'individual', 'telegram')
    sg.enable()

    hw.enable_streaming()

    sg.input('input 1', 1)
    reports = hw.wait_reports(1, timeout=0.5)
    assert len(reports) == 1
    assert reports[0].visible_readings[0].value == 1

    sg.input('input 1', 2)
    reports = hw.wait_reports(1, timeout=0.5)
    assert len(reports) == 1
    assert reports[0].visible_readings[0].value == 2


def test_rpc_engine(rpc_sg):
    """Ensure that our rpc executor works.

    This test sensorgraph calls an rpc that returns an incrementing counter on
    each call.
    """

    sg, hw, _device = rpc_sg
    sg.enable()

    assert sg.count_readings()['streaming'] == 0

    sg.input('input 1', 0)
    assert sg.count_readings()['streaming'] == 1
    sg.input('input 1', 0)
    assert sg.count_readings()['streaming'] == 2

    values = sg.download_stream('output 1')
    assert [x.value for x in values] == [0, 1]
