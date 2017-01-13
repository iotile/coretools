import unittest
import os
import pytest
from iotile.core.exceptions import *
from iotile.core.hw.reports.report import IOTileReading

def test_no_id():
    reading = IOTileReading(0, 1, 2)
    assert reading.raw_time == 0
    assert reading.stream == 1
    assert reading.value == 2
    assert reading.reading_id == reading.InvalidReadingID

def test_with_id():
    reading = IOTileReading(0, 1, 2, reading_id=5)
    assert reading.raw_time == 0
    assert reading.stream == 1
    assert reading.value == 2
    assert reading.reading_id == 5
