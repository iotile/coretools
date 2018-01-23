from builtins import str
import pytest

from iotile.sg.node_descriptor import parse_node_descriptor, parse_binary_descriptor
from iotile.sg.model import DeviceModel
from iotile.sg import SensorGraph, SensorLog, DataStream

def test_basic_parsing():
    """Make sure we can parse a basic node description."""

    node, inputs, processing = parse_node_descriptor('(input 1 always && input 2 when count >= 1) => buffered node 1 using copy_all_a', DeviceModel())

    assert processing == u'copy_all_a'
    assert str(node.stream) == u'buffered 1'
    assert str(inputs[0][0]) == u'input 1'
    assert inputs[0][1] is None

    assert str(inputs[1][0]) == u'input 2'
    assert inputs[1][1] is not None

def test_string_generation():
    """Make sure we can print nodes."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(input 1 always && input 2 when count >= 1) => buffered node 1 using copy_all_a')
    assert str(sg.nodes[-1]) == u'(input 1 always && input 2 when count >= 1) => buffered 1 using copy_all_a'

    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)
    sg.add_node('(input 1 when value < 0x10) => buffered node 1 using copy_all_a')
    assert str(sg.nodes[-1]) == u'(input 1 when value < 16) => buffered 1 using copy_all_a'


def test_binary_parsing():
    """Make sure we can parse binary node descriptors."""

    bin_node = b'\x00\x00\x00\x00\x00\x00\x00\x00\x0f\x10\x008\xff\xff\x00\n\n\x00\x00\x00'
    str_node = parse_binary_descriptor(bin_node)
    assert str_node == '(system input 0 always) => unbuffered 15 using copy_latest_a'

    bin_node = b'\x00\x00\x00\x00\x01\x00\x00\x00\x01\x00\x010\x020\x02\n\x05\x00\x00\x00'
    str_node = parse_binary_descriptor(bin_node)
    assert str_node == '(input 1 always && input 2 when count >= 1) => buffered 1 using copy_all_a'
