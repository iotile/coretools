"""Test to make sure we can create and use SensorGraph objects."""

from iotile.sg import SensorGraph, DeviceModel, SensorLog, DataStream, SlotIdentifier
from iotile.sg.known_constants import config_fast_tick_secs
from iotile.core.hw.reports import IOTileReading


def test_basic_sensorgraph():
    """Make sure we can parse, load and run a basic sensor graph."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(input 1 always && input 2 when count >= 1) => unbuffered 1 using copy_all_a')
    sg.process_input(DataStream.FromString('input 1'), IOTileReading(0, 1, 1), rpc_executor=None)
    sg.process_input(DataStream.FromString('input 2'), IOTileReading(0, 1, 1), rpc_executor=None)

    assert sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 1')).value == 1


def test_usertick():
    """Make sure we properly can set the user tick input."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    assert sg.get_tick('fast') == 0

    sg.add_config(SlotIdentifier.FromString('controller'), config_fast_tick_secs, 'uint32_t', 1)
    assert sg.get_tick('fast') == 1


def test_iteration():
    """Make sure we can iterate over the graph."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(input 1 always && input 2 when count >= 1) => unbuffered 1 using copy_all_a')
    sg.add_node('(input 1 always && input 3 when count >= 1) => unbuffered 2 using copy_all_a')
    sg.add_node('(unbuffered 2 always && unbuffered 1 always) => unbuffered 3 using copy_all_a')
    sg.add_node('(unbuffered 1 always) => unbuffered 3 using copy_all_a')

    iterator = sg.iterate_bfs()

    node1, in1, out1 = next(iterator)
    assert str(node1.stream) == u'unbuffered 1'
    assert len(in1) == 0
    assert len(out1) == 2
    assert str(out1[0].stream) == u'unbuffered 3'
    assert str(out1[1].stream) == u'unbuffered 3'

    node1, in1, out1 = next(iterator)
    assert str(node1.stream) == u'unbuffered 2'
    assert len(in1) == 0
    assert len(out1) == 1
    assert str(out1[0].stream) == u'unbuffered 3'

    node1, in1, out1 = next(iterator)
    assert str(node1.stream) == u'unbuffered 3'
    assert len(in1) == 2
    assert len(out1) == 0
    assert str(in1[0].stream) == u'unbuffered 2'
    assert str(in1[1].stream) == u'unbuffered 1'

    node1, in1, out1 = next(iterator)
    assert str(node1.stream) == u'unbuffered 3'
    assert len(in1) == 1
    assert len(out1) == 0
    assert str(in1[0].stream) == u'unbuffered 1'
