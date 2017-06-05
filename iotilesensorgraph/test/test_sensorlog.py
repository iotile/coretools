import pytest

from iotile.sg.model import DeviceModel
from iotile.sg.sensor_log import SensorLog
from iotile.sg import DataStreamSelector, DataStream, StreamEmptyError
from iotile.core.hw.reports import IOTileReading


def test_counter_walker():
    """Make sure counter walkers work correctly."""

    model = DeviceModel()
    log = SensorLog(model=model)

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

    model = DeviceModel()
    log = SensorLog(model=model)

    walk = log.create_walker(DataStreamSelector.FromString('unbuffered 1'))
    stream = DataStream.FromString('unbuffered 1')

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

    model = DeviceModel()
    log = SensorLog(model=model)

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


def test_storage_walker():
    """Make sure the storage walker works."""

    model = DeviceModel()
    log = SensorLog(model=model)


    walk = log.create_walker(DataStreamSelector.FromString('buffered 1'))
    stream = DataStream.FromString('buffered 1')
    
    storage_size = model.get('max_storage_buffer')
    erase_size = model.get('buffer_erase_size')

    for i in range(0, storage_size):
        reading = IOTileReading(0, stream.encode(), i)
        log.push(stream, reading)

        assert walk.count() == (i + 1)

    # Make sure the overwrite happens correctly
    old_count = walk.count()
    reading = IOTileReading(0, stream.encode(), storage_size)
    log.push(stream, reading)
    assert walk.count() == (old_count - erase_size + 1)


def test_storage_streaming_walkers():
    """Make sure the storage and streaming walkers work simultaneously."""

    model = DeviceModel()
    log = SensorLog(model=model)


    storage_walk = log.create_walker(DataStreamSelector.FromString('buffered 1'))
    output_walk = log.create_walker(DataStreamSelector.FromString('output 1'))
    storage1 = DataStream.FromString('buffered 1')
    storage2 = DataStream.FromString('buffered 2')
    output1 = DataStream.FromString('output 1')
    output2 = DataStream.FromString('output 2')

    assert storage_walk.offset == 0
    assert output_walk.offset == 0

    for i in range(0, 5000):
        reading = IOTileReading(0, 0, i)
        log.push(storage1, reading)
        log.push(storage2, reading)
        log.push(output1, reading)
        log.push(output2, reading)

        assert storage_walk.count() == (i + 1)
        assert output_walk.count() == (i + 1)
        assert storage_walk.offset == 0
        assert output_walk.offset == 0

    for i in range(0, 5000):
        reading1 = storage_walk.pop()
        reading2 = output_walk.pop()

        assert reading1.value == i
        assert reading1.stream == storage1.encode()
        assert reading2.value == i
        assert reading2.stream == output1.encode()
        assert storage_walk.offset == (2 * i) + 1
        assert output_walk.offset == (2* i) + 1

    log.clear()

    assert storage_walk.count() == 0
    assert storage_walk.offset == 0

    assert output_walk.count() == 0
    assert output_walk.offset == 0
