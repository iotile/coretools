from datetime import datetime
from iotile.core.hw.reports.report import IOTileReading, IOTileEvent


def test_no_id():
    """Test readings with no reading_id."""
    reading = IOTileReading(0, 1, 2)
    assert reading.raw_time == 0
    assert reading.stream == 1
    assert reading.value == 2
    assert reading.reading_id == reading.InvalidReadingID

def test_with_id():
    """Test readings with a reading_id."""
    reading = IOTileReading(0, 1, 2, reading_id=5)
    assert reading.raw_time == 0
    assert reading.stream == 1
    assert reading.value == 2
    assert reading.reading_id == 5


def test_timestamp():
    """Test readings with a timestamp."""

    time = datetime.utcnow()
    reading = IOTileReading(0, 1, 2, reading_id=5, reading_time=time)
    assert reading.reading_time == time

    reading2 = IOTileReading.FromDict(reading.asdict())
    assert reading2 == reading


def test_event():
    """Make sure IOTileEvent works."""

    event = IOTileEvent(0, 1, {'test': 'a'}, {'test 2': 1})

    assert event.raw_time == 0
    assert event.stream == 1
    assert event.summary_data == {'test': 'a'}
    assert event.raw_data == {'test 2': 1}

    asdict = event.asdict()
    event = IOTileEvent.FromDict(asdict)

    assert event.raw_time == 0
    assert event.stream == 1
    assert event.summary_data == {'test': 'a'}
    assert event.raw_data == {'test 2': 1}
