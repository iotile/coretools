import pytest
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg.slot import SlotIdentifier
from iotile.sg.known_constants import config_user_tick_secs
from iotile.sg import DeviceModel, SensorLog, SensorGraph, DataStream
from iotile.core.hw.reports import IOTileReading

@pytest.fixture
def basic_sg():
    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(system input 2 always) => unbuffered 1 using copy_all_a')

    return sg


@pytest.fixture
def usertick_sg():
    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(system input 3 always) => counter 1 using copy_latest_a')
    sg.add_config(SlotIdentifier.FromString('controller'), config_user_tick_secs, 'uint32_t', 2)

    return sg


@pytest.fixture
def callrpc_sg():
    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(system input 2 always && constant 1 always) => unbuffered 2 using call_rpc')
    log.push(DataStream.FromString('constant 1'), IOTileReading(0, 0, 0x000a8000))

    return sg

def test_basic_sim(basic_sg):
    """Make sure we can run a very simple sensor graph and have it work."""

    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 1000 seconds')
    sim.run(basic_sg)

    # Make sure the sensor graph ran correctly
    last_input = basic_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = basic_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 1'))

    assert last_input.value == 1000
    assert last_output.value == 1000
    assert sim.tick_count == 1000


def test_rpc_sim(callrpc_sg):
    """Make sure we can run a very simple sensor graph and have it work."""

    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 1000 seconds')
    sim.run(callrpc_sg)

    # Make sure the sensor graph ran correctly
    last_input = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 2'))

    assert last_input.value == 1000
    assert last_output.value == 0


def test_multiple_run_calls(callrpc_sg):
    """Make sure we can call run multiple times."""

    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 100 seconds')

    sim.run(callrpc_sg)

    # Make sure the sensor graph ran correctly
    last_input = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 2'))

    assert last_input.value == 100
    assert last_output.value == 0

    sim.run(callrpc_sg)

    # Make sure the sensor graph ran correctly
    last_input = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 2'))

    assert last_input.value == 200
    assert last_output.value == 0


def test_usertick(usertick_sg):
    """Make sure we receive user ticks in the simulation."""

    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 100 seconds')

    sim.run(usertick_sg)

    # Make sure the sensor graph ran correctly
    last_input = usertick_sg.sensor_log.inspect_last(DataStream.FromString('system input 3'))
    last_output = usertick_sg.sensor_log.inspect_last(DataStream.FromString('counter 1'))

    assert last_input.value == 100
    assert last_output.value == 100

    sim.run(usertick_sg)

    # Make sure the sensor graph ran correctly
    last_input = usertick_sg.sensor_log.inspect_last(DataStream.FromString('system input 3'))
    last_output = usertick_sg.sensor_log.inspect_last(DataStream.FromString('counter 1'))

    assert last_input.value == 200
    assert last_output.value == 200
