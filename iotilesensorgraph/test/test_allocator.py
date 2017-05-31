"""Tests to make sure the StreamAllocator works as intended."""

from iotile.sg.parser.stream_allocator import StreamAllocator
from iotile.sg import SensorGraph, DeviceModel, SensorLog, DataStream


def test_stream_allocation():
    """Make sure we can allocate DataStreams."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    # TODO Finish this function
    alloc = StreamAllocator(sg, model=model)

    stream1 = alloc.allocate_stream(DataStream.ConstantType)
    assert len(sg.nodes) == 0

    stream2 = alloc.attach_stream(stream1)
    assert len(sg.nodes) == 0

    stream3 = alloc.attach_stream(stream1)
    assert len(sg.nodes) == 0

    stream4 = alloc.attach_stream(stream1)
    assert len(sg.nodes) == 0

    stream5 = alloc.attach_stream(stream1)
    assert len(sg.nodes) == 1

    assert stream1 == stream2
    assert stream2 == stream3
    assert stream4 == stream1
    assert stream5 != stream1
