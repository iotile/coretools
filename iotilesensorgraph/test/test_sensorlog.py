import pytest

from iotile.sg.sensor_log import SensorLog
from iotile.sg import DataStreamSelector, DataStream, StreamEmptyError
from iotile.core.hw.reports import IOTileReading


def test_counter_walker():
    """Make sure counter walkers work correctly."""

    log = SensorLog()

    walk = log.create_walker(DataStreamSelector.FromString('counter 1'))
    stream = DataStream.FromString('counter 1')
    reading = IOTileReading(0, 1, 1)

    assert walk.count() == 0
    log.push(stream, IOTileReading(0, 1, 1))
    assert walk.count() == 1
    assert walk.peek().value == 1

    log.push(stream, IOTileReading(0, 1, 3))
    assert walk.count() == 2
    assert walk.peek().value == 3

    val = walk.pop()
    assert walk.count() == 1
    assert val.value == 3

    val = walk.pop()
    assert walk.count() == 0
    assert val.value == 3

    with pytest.raises(StreamEmptyError):
        walk.pop()


def test_unbuffered_walker():
    """Make sure unbuffered walkers hold only 1 reading."""

    log = SensorLog()

    walk = log.create_walker(DataStreamSelector.FromString('unbuffered 1'))
    stream = DataStream.FromString('unbuffered 1')
    reading = IOTileReading(0, 1, 1)

    assert walk.count() == 0
    log.push(stream, IOTileReading(0, 1, 1))
    assert walk.count() == 1
    assert walk.peek().value == 1

    log.push(stream, IOTileReading(0, 1, 3))
    assert walk.count() == 1
    assert walk.peek().value == 3

    val = walk.pop()
    assert walk.count() == 0
    assert val.value == 3

    with pytest.raises(StreamEmptyError):
        walk.pop()


def test_constant_walker():
    """Make sure constant walkers can be read any number of times."""

    log = SensorLog()

    walk = log.create_walker(DataStreamSelector.FromString('constant 1'))
    stream = DataStream.FromString('constant 1')
    reading = IOTileReading(0, 1, 1)

    log.push(stream, reading)
    assert walk.count() == 0xFFFFFFFF

    log.push(stream, reading)
    assert walk.count() == 0xFFFFFFFF

    val = walk.pop()
    assert walk.count() == 0xFFFFFFFF

    val = walk.pop()
    assert walk.count() == 0xFFFFFFFF
