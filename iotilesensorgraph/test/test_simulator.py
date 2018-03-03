import pytest
from typedargs.exceptions import ArgumentError
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg.sim.stimulus import SimulationStimulus
from iotile.sg.slot import SlotIdentifier
from iotile.sg.known_constants import config_fast_tick_secs, config_tick1_secs, config_tick2_secs
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
    sg.add_config(SlotIdentifier.FromString('controller'), config_fast_tick_secs, 'uint32_t', 2)

    return sg


@pytest.fixture
def tick1_sg():
    """A sensorgrah that listens to tick1."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(system input 5 always) => counter 1 using copy_latest_a')
    sg.add_config(SlotIdentifier.FromString('controller'), config_tick1_secs, 'uint32_t', 2)

    return sg


@pytest.fixture
def tick2_sg():
    """A sensorgrah that listens to tick1."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(system input 6 always) => counter 1 using copy_latest_a')
    sg.add_config(SlotIdentifier.FromString('controller'), config_tick2_secs, 'uint32_t', 2)

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

    sim = SensorGraphSimulator(basic_sg)
    sim.stop_condition('run_time 1000 seconds')
    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = basic_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = basic_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 1'))

    assert last_input.value == 1000
    assert last_output.value == 1000
    assert sim.tick_count == 1000


def test_rpc_sim(callrpc_sg):
    """Make sure we can run a very simple sensor graph and have it work."""

    sim = SensorGraphSimulator(callrpc_sg)
    sim.stop_condition('run_time 1000 seconds')
    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 2'))

    assert last_input.value == 1000
    assert last_output.value == 0


def test_multiple_run_calls(callrpc_sg):
    """Make sure we can call run multiple times."""

    sim = SensorGraphSimulator(callrpc_sg)
    sim.stop_condition('run_time 100 seconds')

    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 2'))

    assert last_input.value == 100
    assert last_output.value == 0

    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = callrpc_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 2'))

    assert last_input.value == 200
    assert last_output.value == 0


def test_usertick(usertick_sg):
    """Make sure we receive user ticks in the simulation."""

    sim = SensorGraphSimulator(usertick_sg)
    sim.stop_condition('run_time 100 seconds')

    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = usertick_sg.sensor_log.inspect_last(DataStream.FromString('system input 3'))
    last_output = usertick_sg.sensor_log.inspect_last(DataStream.FromString('counter 1'))

    assert last_input.value == 100
    assert last_output.value == 100

    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = usertick_sg.sensor_log.inspect_last(DataStream.FromString('system input 3'))
    last_output = usertick_sg.sensor_log.inspect_last(DataStream.FromString('counter 1'))

    assert last_input.value == 200
    assert last_output.value == 200


def test_tick1(tick1_sg):
    """Make sure we receive tick_1 ticks in the simulation."""

    assert tick1_sg.get_tick('user1') == 2

    sim = SensorGraphSimulator(tick1_sg)
    sim.stop_condition('run_time 100 seconds')

    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = tick1_sg.sensor_log.inspect_last(DataStream.FromString('system input 5'))
    last_output = tick1_sg.sensor_log.inspect_last(DataStream.FromString('counter 1'))

    assert last_input.value == 100
    assert last_output.value == 100

    sim.run()

    # Make sure the sensor graph ran correctly
    last_input = tick1_sg.sensor_log.inspect_last(DataStream.FromString('system input 5'))
    last_output = tick1_sg.sensor_log.inspect_last(DataStream.FromString('counter 1'))

    assert last_input.value == 200
    assert last_output.value == 200


def test_stimulus_parsing():
    """Make sure we can parse stimulus strings."""

    stim1 = SimulationStimulus.FromString('system input 1024 = 10')
    assert stim1.time == 0
    assert stim1.value == 10
    assert str(stim1.stream) == 'system input 1024'

    stim2 = SimulationStimulus.FromString('50 seconds: input 1 = 0x5')
    assert stim2.time == 50
    assert stim2.value == 5
    assert str(stim2.stream) == 'input 1'

    stim3 = SimulationStimulus.FromString('11 minutes: input 1034 = 1')
    assert stim3.time == 11*60

    with pytest.raises(ArgumentError):
        SimulationStimulus.FromString("Unknown")

    with pytest.raises(ArgumentError):
        SimulationStimulus.FromString('unbuffered 1 = 1')

