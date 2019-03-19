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
UTCAssigner uses various other methods to infer an approximate UTC timestamp,
returning confidence metrics along with the assigned value.
"""

import datetime
import logging
from typedargs.exceptions import ArgumentError
from sortedcontainers import SortedKeyList
from .signed_list_format import SignedListReport
from .report import IOTileReading


class _TimeAnchor:
    """Internal class for storing a utc reference point."""

    __slots__ = ('uptime', 'utc', 'reading_id', 'is_break', 'exact')

    def __init__(self, reading_id, uptime=None, utc=None, is_break=False, exact=False):
        self.uptime = uptime
        self.utc = utc
        self.reading_id = reading_id
        self.is_break = is_break
        self.exact = exact

    def copy(self):
        """Return a copy of this _TimeAnchor."""
        return _TimeAnchor(self.reading_id, self.uptime, self.utc, self.is_break, self.exact)


class UTCAssignment:
    """Data class recording the assignment of a UTC timestamp.

    Args:
        reading_id (int): The id of the reading that we are assigning
        utc (datetime): UTC datetime that we assigned to the reading
        found (bool): Whether we found the exact reading_id in our
            set of anchor points or inferred it as between two other
            reading ids
        exact (bool): Whether we believe the UTC assignment is exact
            or approximate.
        crossed_break (bool): Whether the assignment required crossing
            an uptime break such as a device reset.  This can introduce
            a lot of ambiguity into the result since the time-break could
            be arbitrarily long.
    """

    _Y2KReference = datetime.datetime(2000, 1, 1)
    _EpochReference = datetime.datetime(1970, 1, 1)

    __slots__ = ('reading_id', 'utc', 'found_id', 'exact', 'crossed_break', 'rtc_value')

    def __init__(self, reading_id, utc, found, exact, crossed_break):
        self.reading_id = reading_id
        self.utc = utc
        self.found_id = found
        self.exact = exact
        self.crossed_break = crossed_break

        rtc_value = int((utc - self._Y2KReference).total_seconds())
        self.rtc_value = rtc_value | (1 << 31)

    @property
    def epoch_value(self):
        """The number of seconds since the Unix Epoch."""

        return int((self.utc - self._EpochReference).total_seconds())

    def __str__(self):
        return "%s (reading_id=%08X, exact=%s, crossed_break=%s)" % \
               (self.utc, self.reading_id, self.exact, self.crossed_break)


class UTCAssigner:
    """Helper class to assign UTC timestamps to device readings.

    This class contains logic to infer UTC timestamps for readings that are
    stamped in uptime only by looking for nearby readings for which the UTC
    timestamp is known.  The relative offset between these anchor points and
    the reading in question is then used to infer the UTC timestamp from the
    anchor point either exactly or approximately.

    The underlying truth that this class relies on is the fact that all
    readings produced by an IOTile device have a mononotically increasing
    reading_id that can be used to absolutely order them.  In contrast to the
    readings timestamp, which may reset to 0 if the device reboots and does
    not have a realtime clock, the reading_id is guaranteed to never decrease.
    """

    _Y2KReference = datetime.datetime(2000, 1, 1)
    _EpochReference = datetime.datetime(1970, 1, 1)

    def __init__(self):
        self._anchor_points = SortedKeyList(key=lambda x: x.reading_id)
        self._prepared = False
        self._anchor_streams = {}
        self._break_streams = set()
        self._logger = logging.getLogger(__name__)

        self._known_converters = {
            'rtc': UTCAssigner._convert_rtc_anchor,
            'epoch': UTCAssigner._convert_epoch_anchor
        }

    def _load_known_breaks(self):
        self._break_streams.add(0x5C00)

    def anchor_stream(self, stream_id, converter="rtc"):
        """Mark a stream as containing anchor points."""

        if isinstance(converter, str):
            converter = self._known_converters.get(converter)

            if converter is None:
                raise ArgumentError("Unknown anchor converter string: %s" % converter,
                                    known_converters=list(self._known_converters))

        self._anchor_streams[stream_id] = converter

    def id_range(self):
        """Get the range of archor reading_ids.

        Returns:
            (int, int): The lowest and highest reading ids.

            If no reading ids have been loaded, (0, 0) is returned.
        """

        if len(self._anchor_points) == 0:
            return (0, 0)

        return (self._anchor_points[0].reading_id, self._anchor_points[-1].reading_id)

    @classmethod
    def convert_rtc(cls, timestamp):
        """Convert a number of seconds since 1/1/2000 to UTC time."""

        if timestamp & (1  << 31):
            timestamp &= ~(1 << 31)

        delta = datetime.timedelta(seconds=timestamp)
        return cls._Y2KReference + delta

    @classmethod
    def _convert_rtc_anchor(cls, reading):
        """Convert a reading containing an RTC timestamp to datetime."""

        return cls.convert_rtc(reading.value)

    @classmethod
    def _convert_epoch_anchor(cls, reading):
        """Convert a reading containing an epoch timestamp to datetime."""

        delta = datetime.timedelta(seconds=reading.value)
        return cls._EpochReference + delta

    def add_point(self, reading_id, uptime=None, utc=None, is_break=False):
        """Add a time point that could be used as a UTC reference."""

        if reading_id == 0:
            return

        if uptime is None and utc is None:
            return

        if uptime is not None and uptime & (1 << 31):
            if utc is not None:
                return

            uptime &= ~(1 << 31)

            utc = self.convert_rtc(uptime)
            uptime = None

        anchor = _TimeAnchor(reading_id, uptime, utc, is_break, exact=utc is not None)

        if anchor in self._anchor_points:
            return

        self._anchor_points.add(anchor)
        self._prepared = False

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

    def assign_utc(self, reading_id, uptime=None, prefer="before"):
        """Assign a utc datetime to a reading id.

        This method will return an object with assignment information or None
        if a utc value cannot be assigned.  The assignment object returned
        contains a utc property that has the asssigned UTC as well as other
        properties describing how reliable the assignment is.

        Args:
            reading_id (int): The monotonic reading id that we wish to assign
                a utc timestamp to.
            uptime (int): Optional uptime that should be associated with the
                reading id.  If this is not specified and the reading_id is
                found in the anchor points passed to this class then the
                uptime from the corresponding anchor point will be used.
            prefer (str): There are two possible directions that can be used
                to assign a UTC timestamp (the nearest anchor before or after the
                reading).  If both directions are of similar quality, the choice
                is arbitrary.  Passing prefer="before" will use the anchor point
                before the reading.  Passing prefer="after" will use the anchor
                point after the reading.  Default: before.

        Returns:
            UTCAssignment: The assigned UTC time or None if assignment is impossible.
        """

        if prefer not in ("before", "after"):
            raise ArgumentError("Invalid prefer parameter: {}, must be 'before' or 'after'".format(prefer))

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
                return UTCAssignment(reading_id, last.utc, found_id, exact, crossed_break)

        left_assign = self._fix_left(reading_id, last, i, found_id)
        if left_assign is not None and left_assign.exact:
            return left_assign

        right_assign = self._fix_right(reading_id, last, i, found_id)
        if right_assign is not None and right_assign.exact:
            return right_assign

        return self._pick_best_fix(left_assign, right_assign, prefer)

    def ensure_prepared(self):
        """Calculate and cache UTC values for all exactly known anchor points."""

        if self._prepared:
            return

        exact_count = 0
        fixed_count = 0
        inexact_count = 0

        self._logger.debug("Preparing UTCAssigner (%d total anchors)", len(self._anchor_points))

        for curr in self._anchor_points:
            if not curr.exact:
                assignment = self.assign_utc(curr.reading_id, curr.uptime)
                if assignment is not None and assignment.exact:
                    curr.utc = assignment.utc
                    curr.exact = True
                    fixed_count += 1
                else:
                    inexact_count += 1
            else:
                exact_count += 1

        self._logger.debug("Prepared UTCAssigner with %d reference points, "
                           "%d exact anchors and %d inexact anchors",
                           exact_count, fixed_count, inexact_count)

        self._prepared = True

    def fix_report(self, report, errors="drop", prefer="before"):
        """Perform utc assignment on all readings in a report.

        The returned report will have all reading timestamps in UTC. This only
        works on SignedListReport objects.  Note that the report should
        typically have previously been added to the UTC assigner using
        add_report or no reference points from the report will be used.

        Args:
            report (SignedListReport): The report that we should fix.
            errors (str): The behavior that we should have when we can't
                fix a given reading.  The only currently support behavior is
                drop, which means that the reading will be dropped and not
                included in the new report.
            prefer (str): Whether to prefer fixing readings by looking for
                reference points after the reading or before, all other things
                being equal.  See the description of ``assign_utc``.

        Returns:
            SignedListReport: The report with UTC timestamps.
        """

        if not isinstance(report, SignedListReport):
            raise ArgumentError("Report must be a SignedListReport", report=report)

        if errors not in ('drop',):
            raise ArgumentError("Unknown errors handler: {}, supported=['drop']".format(errors))

        self.ensure_prepared()

        fixed_readings = []
        dropped_readings = 0

        for reading in report.visible_readings:
            assignment = self.assign_utc(reading.reading_id, reading.raw_time, prefer=prefer)

            if assignment is None:
                dropped_readings += 1
                continue

            fixed_reading = IOTileReading(assignment.rtc_value, reading.stream, reading.value,
                                          reading_time=assignment.utc, reading_id=reading.reading_id)
            fixed_readings.append(fixed_reading)

        fixed_report = SignedListReport.FromReadings(report.origin, fixed_readings, report_id=report.report_id,
                                                     selector=report.streamer_selector, streamer=report.origin_streamer,
                                                     sent_timestamp=report.sent_timestamp)
        fixed_report.received_time = report.received_time

        if dropped_readings > 0:
            self._logger.warning("Dropped %d readings of %d when fixing UTC timestamps in report 0x%08X for device 0x%08X",
                                 dropped_readings, len(report.visible_readings), report.report_id, report.origin)

        return fixed_report

    def _pick_best_fix(self, before, after, prefer):
        if before is None and after is None:
            return None

        if after is None:
            return before

        if before is None:
            return after

        if after.crossed_break and not before.crossed_break:
            return before

        if before.crossed_break and not after.crossed_break:
            return after

        if before.exact and not after.exact:
            return before

        if after.exact and not before.exact:
            return after

        if prefer == 'before':
            return before

        return after

    def _fix_right(self, reading_id, last, start, found_id):
        """Fix a reading by looking for the nearest anchor point after it."""

        accum_delta = 0
        exact = True
        crossed_break = False

        if start == len(self._anchor_points) - 1:
            return None

        for curr in self._anchor_points.islice(start + 1):
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

    def _fix_left(self, reading_id, last, start, found_id):
        """Fix a reading by looking for the nearest anchor point before it."""

        accum_delta = 0
        exact = True
        crossed_break = False

        if start == 0:
            return None

        for curr in self._anchor_points.islice(None, start - 1, reverse=True):
            if curr.uptime is None or last.uptime is None:
                exact = False
            elif curr.is_break or last.uptime < curr.uptime:
                exact = False
                crossed_break = True
            else:
                accum_delta += last.uptime - curr.uptime

            if curr.utc is not None:
                time_delta = datetime.timedelta(seconds=accum_delta)
                return UTCAssignment(reading_id, curr.utc + time_delta, found_id, exact, crossed_break)

            last = curr

        return None
