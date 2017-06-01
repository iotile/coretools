import os
import pytest
from iotile.sg.exceptions import SensorGraphSyntaxError
from iotile.sg import DataStream, DeviceModel, DataStreamSelector
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.sim import SensorGraphSimulator
import iotile.sg.parser.language as language


@pytest.fixture
def parser():
    return SensorGraphFileParser()


def get_path(name):
    return os.path.join(os.path.dirname(__file__), 'sensor_graphs', name)


def test_every_block_compilation(parser):
    """Make sure we can compile a simple every block."""

    parser.parse_file(get_path(u'basic_every_1min.sgf'))

    model = DeviceModel()
    parser.compile(model=model)

    sg = parser.sensor_graph
    log = sg.sensor_log
    for x in sg.dump_nodes():
        print(x)

    assert len(sg.nodes) == 5

    # Now make sure it produces the right output
    counter15 = log.create_walker(DataStreamSelector.FromString('counter 15'))
    counter16 = log.create_walker(DataStreamSelector.FromString('counter 16'))

    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 120 seconds')
    sim.run(sg)

    assert counter15.count() == 2
    assert counter16.count() == 2


def test_every_block_splitting(parser):
    """Make sure we can split nodes in an every block."""

    parser.parse_file(get_path(u'basic_every_split.sgf'))

    model = DeviceModel()
    parser.compile(model=model)

    sg = parser.sensor_graph
    log = sg.sensor_log
    for x in sg.dump_nodes():
        print(x)

    assert len(sg.nodes) == 8

    # Now make sure it produces the right output
    counter15 = log.create_walker(DataStreamSelector.FromString('counter 15'))
    counter16 = log.create_walker(DataStreamSelector.FromString('counter 16'))
    counter17 = log.create_walker(DataStreamSelector.FromString('counter 16'))
    counter18 = log.create_walker(DataStreamSelector.FromString('counter 16'))

    sim = SensorGraphSimulator()
    sim.stop_condition('run_time 120 seconds')
    sim.run(sg)

    print([str(x) for x in log._last_values.keys()])

    assert counter15.count() == 2
    assert counter16.count() == 2
    assert counter17.count() == 2
    assert counter18.count() == 2
