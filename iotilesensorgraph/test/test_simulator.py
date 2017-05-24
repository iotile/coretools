import pytest
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg import DeviceModel, SensorLog, SensorGraph, DataStream

@pytest.fixture
def basic_sg():
    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(system input 2 always) => unbuffered 1 using copy_all_a')

    return sg

def test_basic_sim(basic_sg):
    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 1000 seconds')
    sim.run(basic_sg)

    # Make sure the sensor graph ran correctly
    last_input = basic_sg.sensor_log.inspect_last(DataStream.FromString('system input 2'))
    last_output = basic_sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 1'))

    assert last_input.value == 1000
    assert last_output.value == 1000
