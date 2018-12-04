"""Helper module for assigning UTC times to readings without a realtime clock.

Some IOTile devices timestamp their readings in uptime rather than UTC time,
which means a conversion process is needed to convert to absolute time from
the device's local reference time.

The UTCAssigner class provides a reference implementation of this conversion
process.  The conversion algorithm looks for known points in time where both
the device uptime and absolute UTC time are known.  These points are known as
anchors.  For any other reading, the difference in uptime between it and the
closest anchor is added to the absolute UTC time of the anchor to calculate
the absolute UTC time of the reading.

In the easy case, when there are no device resets between the reading you want
to convert and an anchor point and uptimes are known for each point, this
reconstruction process is exact.

However, in the general case, an exact assignment is not possible and
UTCAssigner uses various other methods to infer an appoximate UTC timestamp,
returning confidence metrics along with the assigned value.
"""

import datetime
from typedargs.exceptions import ArgumentError
from sortedcontainers import SortedKeyList
from .signed_list_format import SignedListReport


class _TimeAnchor(object):
    """Internal class for storing a utc reference point."""

    __slots__ = ('uptime', 'utc', 'reading_id', 'is_break')

    def __init__(self, reading_id, uptime=None, utc=None, is_break=False):
        self.uptime = uptime
        self.utc = utc
        self.reading_id = reading_id
        self.is_break = is_break

    def copy(self):
        return _TimeAnchor(self.reading_id, self.uptime, self.utc, self.is_break)


class UTCAssignment(object):
    _Y2KReference = datetime.datetime(2000, 1, 1)

    def __init__(self, reading_id, utc, found, exact, crossed_break):
        self.reading_id = reading_id
        self.utc = utc
        self.found_id = found
        self.exact = exact
        self.crossed_break = crossed_break

        rtc_value = int((utc - self._Y2KReference).total_seconds())
        self.rtc_value = rtc_value | (1 << 31)

    def __str__(self):
        return "%s (reading_id=%08X, exact=%s, crossed_break=%s)" % (self.utc, self.reading_id, self.exact, self.crossed_break)


class UTCAssigner(object):
    """Helper class to assign UTC timestamps to device readings."""

    _Y2KReference = datetime.datetime(2000, 1, 1)

    def __init__(self):
        self._anchor_points = SortedKeyList(key=lambda x: x.reading_id)
        self._anchor_streams = {}
        self._break_streams = set()

        self._known_converters = {
            'rtc': UTCAssigner.convert_rtc
        }

    def _load_known_breaks(self):
        self._break_streams.add(0x5C00)

    def anchor_stream(self, stream_id, converter="rtc"):
        """Mark a stream as containing anchor points."""

        if isinstance(converter, str):
            converter = self._known_converters.get(converter)

            if converter is None:
                raise ArgumentError("Unknown anchor converter string: %s" % converter, known_converters=list(self._known_converters))

        self._anchor_streams[stream_id] = converter

    @classmethod
    def convert_rtc(cls, timestamp):
        """Convert a number of seconds since 1/1/2000 to UTC time."""

        if timestamp & (1  << 31):
            timestamp &= ~(1 << 31)

        delta = datetime.timedelta(seconds=timestamp)
        return cls._Y2KReference + delta

    def add_point(self, reading_id, uptime=None, utc=None, is_break=False):
        """Add a time point that could be used as a UTC reference."""

        if reading_id == 0:
            return

        if uptime is None and utc is None:
            return

        if uptime & (1 << 31):
            if utc is not None:
                return

            uptime &= ~(1 << 31)

            utc = self.convert_rtc(uptime)
            uptime = None

        anchor = _TimeAnchor(reading_id, uptime, utc, is_break)

        if anchor in self._anchor_points:
            return

        self._anchor_points.add(anchor)

    def add_reading(self, reading):
        """Add an IOTileReading."""

        is_break = False
        utc = None

        if reading.stream in self._break_streams:
            is_break = True

        if reading.stream in self._anchor_streams:
            utc = self._anchor_streams[reading.stream](reading)

        self.add_point(reading.reading_id, reading.raw_time, utc, is_break=is_break)

    def add_report(self, report, ignore_errors=False):
        """Add all anchors from a report."""

        if not isinstance(report, SignedListReport):
            if ignore_errors:
                return

            raise ArgumentError("You can only add SignedListReports to a UTCAssigner", report=report)

        for reading in report.visible_readings:
            self.add_reading(reading)

        self.add_point(report.report_id, report.sent_timestamp, report.received_time)

    def assign_utc(self, reading_id, uptime=None):
        """Assign a utc datetime to a reading id.

        This method will return an object with assignment information or None
        if a utc value cannot be assigned.  The assignment object returned
        contains a utc property that has the asssigned UTC as well as other
        properties describing how reliable the assignment is.
        """

        if len(self._anchor_points) == 0:
            return None

        if reading_id > self._anchor_points[-1].reading_id:
            return None

        i = self._anchor_points.bisect_key_left(reading_id)
        found_id = False
        crossed_break = False
        exact = True

        last = self._anchor_points[i].copy()
        if uptime is not None:
            last.uptime = uptime

        if last.reading_id == reading_id:
            found_id = True

            if last.utc is not None:
                return last.utc

        accum_delta = 0
        for curr in self._anchor_points.islice(i + 1):
            if curr.uptime is None or last.uptime is None:
                exact = False
            elif curr.is_break or curr.uptime < last.uptime:
                exact = False
                crossed_break = True
            else:
                accum_delta += curr.uptime - last.uptime

            if curr.utc is not None:
                time_delta = datetime.timedelta(seconds=accum_delta)
                return UTCAssignment(reading_id, curr.utc - time_delta, found_id, exact, crossed_break)

            last = curr

        return None
