"""Time based stimulus class that can be applied to a simulation."""

from __future__ import (unicode_literals, absolute_import, print_function)
from builtins import str
from pyparsing import Optional, Literal, ParseException, ParseSyntaxException
from typedargs.exceptions import ArgumentError
from .stop_conditions import time_interval, number
import iotile.sg.parser.language as language

class SimulationStimulus(object):
    """A simulation stimulus that injects a value at a given time.

    Args:
        time (int): The time in 1 second ticks when this stimulus occurs
        stream (DataStream): The data stream that will be affected.  This
            must be an input stream.
        value (int): The value that will be injected to the given stream.
    """

    def __init__(self, time, stream, value):
        self.time = time
        self.stream = stream
        self.value = value

        if self.stream.stream_type != self.stream.InputType:
            raise ArgumentError("Invalid stimulus applied to non-input stream", stream=self.stream)

    @classmethod
    def FromString(cls, desc):
        """Create a new stimulus from a description string.

        The string must have the format:

        [time: ][system ]input X = Y
        where X and Y are integers.  The time, if given must
        be a time_interval, which is an integer followed by a
        time unit such as second(s), minute(s), etc.

        Args:
            desc (str): A string description of the stimulus.

        Returns:
            SimulationStimulus: The parsed stimulus object.
        """
        if language.stream is None:
            language.get_language()

        parse_exp = Optional(time_interval('time') - Literal(':').suppress()) - language.stream('stream') - Literal('=').suppress() - number('value')

        try:
            data = parse_exp.parseString(desc)
            time = 0
            if 'time' in data:
                time = data['time'][0]

            return SimulationStimulus(time, data['stream'][0], data['value'])
        except (ParseException, ParseSyntaxException):
            raise ArgumentError("Could not parse stimulus descriptor", descriptor=desc)
