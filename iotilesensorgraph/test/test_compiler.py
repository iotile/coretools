import os
import pytest
from iotile.sg.exceptions import SensorGraphSyntaxError
from iotile.sg import DataStream, DeviceModel
from iotile.sg.parser import SensorGraphFileParser
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
    for x in sg.dump_nodes():
        print(x)

    assert len(sg.nodes) == 5

def test_every_block_splitting(parser):
    """Make sure we can split nodes in an every block."""

    parser.parse_file(get_path(u'basic_every_split.sgf'))

    model = DeviceModel()
    parser.compile(model=model)

    sg = parser.sensor_graph
    for x in sg.dump_nodes():
        print(x)

    assert len(sg.nodes) == 8
