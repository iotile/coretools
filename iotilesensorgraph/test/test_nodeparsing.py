from builtins import str
import pytest

from iotile.sg.node_descriptor import parse_node_descriptor
from iotile.sg.model import DeviceModel

def test_basic_parsing():
    """Make sure we can parse a basic node description."""

    node, inputs, processing = parse_node_descriptor('(input 1 always && input 2 when count >= 1) => buffered node 1 using copyA', DeviceModel())

    assert processing == u'copyA'
    assert str(node.stream) == 'buffered 1'
    assert str(inputs[0][0]) == 'input 1'
    assert inputs[0][1] is None

    assert str(inputs[1][0]) == 'input 2'
    assert inputs[1][1] is not None
