"""All of the known stop conditions that we support."""

from pyparsing import Word, Regex, nums, hexnums, Literal, Optional, Group, oneOf, QuotedString, ParseException
from iotile.core.exceptions import ArgumentError

hex_number = (Regex(u'0x[0-9a-fA-F]+')).setParseAction(lambda s, l, t: [int(t[0], 0)])
dec_number = Word(nums).setParseAction(lambda s, l, t: [int(t[0], 10)])
number = hex_number | dec_number

time_unit_multipliers = {
    u'second': 1,
    u'seconds': 1,
    u'minute': 60,
    u'minutes': 60,
    u'hour': 60*60,
    u'hours': 60*60,
    u'day': 60*60*24,
    u'days': 60*60*24,
    u'month': 60*60*24*30,
    u'months': 60*60*24*30,
    u'year': 60*60*24*365,
    u'years': 60*60*24*365,
}
time_unit = oneOf(u"second seconds minute minutes hour hours day days week weeks month months year years")
time_interval = (number + time_unit).setParseAction(lambda s, l, t: [t[0]*time_unit_multipliers[t[1]]])


class StopCondition(object):
    """A condition under which the simulation should stop.

    Subclasses should override the one public method
    named should_stop(self, abs_seconds, rel_seconds, sensor_graph).

    The abs_seconds parameter is the number of seconds that have expired
    since the start of the simulation (over all calls to run).  The
    rel_seconds parameter counts relative seconds inside the current call to run.
    The sensor_graph is the sensor_graph (including data) being simulated.  The function
    should return a bool with True meaning that the simulation
    should stop.

    There should be a second class method, FromString(cls, desc) that
    tries to parse this stop condition from a text string.  The function
    must raise an ArgumentError if it could not match the input string.
    """

    def should_stop(self, abs_second_count, rel_second_count, sensor_graph):
        """Check if this stop condition is fulfilled.

        Args:
            abs_second_count (int): The number of seconds that
                have expired since the start of the simulation.
            second_count (int): The number of seconds that
                have expired since the start of the last `run` calls.
            sensor_graph (SensorGraph): The sensor graph that is
                being simulated, giving access to its stored data.

        Returns:
            bool: True if we should stop, otherwise False
        """

        return False


class TimeBasedStopCondition(StopCondition):
    """Stop the simulation after a fixed period of time.

    This time is relative to the call to `run` so the simulation
    may be continued over multiple run calls, each of which lasts
    for max_time seconds.

    Args:
        max_time (int): The maximum number of seconds to run the
            simulation for.
    """

    def __init__(self, max_time):
        self.max_time = max_time

    def should_stop(self, abs_seconds, rel_seconds, sensor_graph):
        """Check if this stop condition is fulfilled.

        Args:
            second_count (int): The number of seconds that
                have expired since the start of the simulation.
            sensor_graph (SensorGraph): The sensor graph that is
                being simulated, giving access to its stored data.

        Returns:
            bool: True if we should stop, otherwise False
        """

        return rel_seconds >= self.max_time

    @classmethod
    def FromString(cls, desc):
        """Parse this stop condition from a string representation.

        The string needs to match:
        run_time number [seconds|minutes|hours|days|months|years]

        Args:
            desc (str): The description

        Returns:
            TimeBasedStopCondition
        """

        parse_exp = Literal(u'run_time').suppress() + time_interval(u'interval')

        try:
            data = parse_exp.parseString(desc)
            return TimeBasedStopCondition(data[u'interval'][0])
        except ParseException:
            raise ArgumentError(u"Could not parse time based stop condition")
