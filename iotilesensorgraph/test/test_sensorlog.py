import pytest

from iotile.core.exceptions import ArgumentError
from iotile.sg.model import DeviceModel
from iotile.sg.sensor_log import SensorLog
from iotile.sg.exceptions import StorageFullError
from iotile.sg.engine import InMemoryStorageEngine
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


def test_walker_at_beginning():
    """Make sure we can start a walker at the beginning of a stream."""

    model = DeviceModel()
    log = SensorLog(model=model)

    stream = DataStream.FromString('buffered 1')
    reading = IOTileReading(stream.encode(), 0, 1)
    log.push(stream, reading)
    log.push(stream, reading)
    log.push(DataStream.FromString('buffered 2'), reading)

    walk = log.create_walker(DataStreamSelector.FromString('buffered 1'), skip_all=False)
    assert walk.offset == 0
    assert walk.count() == 2


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


def test_storage_scan():
    """Make sure scan_storage works."""

    model = DeviceModel()

    engine = InMemoryStorageEngine(model)
    log = SensorLog(engine, model=model)

    storage1 = DataStream.FromString('buffered 1')
    output1 = DataStream.FromString('output 1')

    for i in range(0, 10):
        reading = IOTileReading(0, 0, i)
        log.push(storage1, reading)

    for i in range(7, 14):
        reading = IOTileReading(0, 0, i)
        log.push(output1, reading)

    shared = [None, 0]

    def _max_counter(i, reading):
        if reading.value > shared[1]:
            shared[0] = i
            shared[1] = reading.value

    # Make sure scanning storage works
    shared = [None, 0]
    count = engine.scan_storage('storage', _max_counter)
    assert count == 10
    assert shared == [9, 9]

    shared = [None, 0]
    count = engine.scan_storage('storage', _max_counter, start=5, stop=9)
    assert count == 5
    assert shared == [9, 9]

    shared = [None, 0]
    count = engine.scan_storage('storage', _max_counter, start=5, stop=8)
    assert count == 4
    assert shared == [8, 8]

    # Make sure scanning steaming works
    shared = [None, 0]
    count = engine.scan_storage('streaming', _max_counter)
    assert count == 7
    assert shared == [6, 13]

    shared = [None, 0]
    count = engine.scan_storage('streaming', _max_counter, start=2, stop=6)
    assert count == 5
    assert shared == [6, 13]

    shared = [None, 0]
    count = engine.scan_storage('streaming', _max_counter, start=2, stop=5)
    assert count == 4
    assert shared == [5, 12]

    # Make sure errors are thrown correctly
    with pytest.raises(ArgumentError):
        engine.scan_storage('other_name', _max_counter)

    with pytest.raises(ArgumentError):
        engine.scan_storage('streaming', _max_counter, stop=7)


def test_seek_walker():
    """Make sure we can seek a walker can count with an offset."""

    model = DeviceModel()
    log = SensorLog(model=model)

    stream = DataStream.FromString('buffered 1')
    reading = IOTileReading(stream.encode(), 0, 1)
    log.push(stream, reading)
    log.push(stream, reading)
    log.push(DataStream.FromString('buffered 2'), reading)
    log.push(stream, reading)

    walk = log.create_walker(DataStreamSelector.FromString('buffered 1'), skip_all=False)
    assert walk.offset == 0
    assert walk.count() == 3

    walk.seek(1)
    assert walk.offset == 1
    assert walk.count() == 2

    # Make sure we can seek to a position corresponding to another stream
    walk.seek(2)
    assert walk.offset == 2
    assert walk.count() == 1


def test_fill_stop():
    """Make sure we can configure SensorLog into fill-stop mode."""

    model = DeviceModel()
    log = SensorLog(model=model)

    storage = DataStream.FromString('buffered 1')
    output = DataStream.FromString('output 1')

    reading = IOTileReading(0, 0, 1)

    # Neither fill-stop
    for _i in range(0, 50000):
        log.push(storage, reading)

    for _i in range(0, 50000):
        log.push(output, reading)

    log.clear()
    log.set_rollover('storage', False)

    with pytest.raises(StorageFullError):
        for _i in range(0, 50000):
            log.push(storage, reading)

    for _i in range(0, 50000):
        log.push(output, reading)

    assert log.count() == (16128, 48720)

    log.clear()
    log.set_rollover('streaming', False)

    with pytest.raises(StorageFullError):
        for _i in range(0, 50000):
            log.push(storage, reading)

    with pytest.raises(StorageFullError):
        for _i in range(0, 50000):
            log.push(output, reading)

    assert log.count() == (16128, 48896)
