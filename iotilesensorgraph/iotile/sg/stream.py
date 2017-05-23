"""Classes for representing and selecting data streams.

Streams are basically FIFOs with a numeric tag to represent their
identity and a series of readings.  There are two key classes:

DataStream: A wrapper around the tag that identifies the stream

DataStreamSelector: An object that selects a specific stream or a
    class of streams.
"""

# For python 2/3 compatibility using future module
from builtins import str
from future.utils import python_2_unicode_compatible
from iotile.core.exceptions import ArgumentError


@python_2_unicode_compatible
class DataStream(object):
    """An immutable specifier of a specific data stream

    Args:
        stream_type (int): The type of the stream
        stream_id (int): The stream identifier
        system (bool): Whether this stream is user defined or
            has global, system-wide meaning.
    """

    BufferedType = 0
    UnbufferedType = 1
    ConstantType = 2
    InputType = 3
    CounterType = 4
    OutputType = 5

    StringToType = {
        u'buffered': 0,
        u'unbuffered': 1,
        u'constant': 2,
        u'input': 3,
        u'counter': 4,
        u'output': 5
    }

    TypeToString = {
        0: u'buffered',
        1: u'unbuffered',
        2: u'constant',
        3: u'input',
        4: u'counter',
        5: u'output'
    }

    def __init__(self, stream_type, stream_id, system=False):
        self.stream_type = stream_type
        self.stream_id = stream_id
        self.system = system

    @property
    def buffered(self):
        return self.stream_type == self.BufferedType or self.stream_type == self.OutputType

    @classmethod
    def FromString(cls, string_rep):
        """Create a DataStream from a string representation.

        The format for stream designators when encoded as strings is:
        [system] (buffered|unbuffered|constant|input|count|output) <integer>

        Args:
            string_rep (str): The string representation to turn into a
                DataStream
        """

        rep = str(string_rep)

        parts = rep.split()
        if len(parts) > 3:
            raise ArgumentError("Too many whitespace separated parts of stream designator", input_string=string_rep)
        elif len(parts) == 3 and parts[0] != u'system':
            raise ArgumentError("Too many whitespace separated parts of stream designator", input_string=string_rep)
        elif len(parts) < 2:
            raise ArgumentError("Too few components in stream designator", input_string=string_rep)

        # Now actually parse the string
        if len(parts) == 3:
            system = True
            stream_type = parts[1]
            stream_id = parts[2]
        else:
            system = False
            stream_type = parts[0]
            stream_id = parts[1]

        try:
            stream_id = int(stream_id, 0)
        except ValueError as exc:
            raise ArgumentError("Could not convert stream id to integer", error_string=str(exc), stream_id=stream_id)

        try:
            stream_type = cls.StringToType[stream_type]
        except KeyError:
            raise ArgumentError("Invalid stream type given", stream_type=stream_type, known_types=cls.StringToType.keys())

        return DataStream(stream_type, stream_id, system)

    def __str__(self):
        type_str = self.TypeToString[self.stream_type]

        if self.system:
            return u'system {} {}'.format(type_str, self.stream_id)

        return u'{} {}'.format(type_str, self.stream_id)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, DataStream):
            raise NotImplemented()

        return self.system == other.system and self.stream_type == other.stream_type and self.stream_id == other.stream_id


@python_2_unicode_compatible
class DataStreamSelector(object):
    """A specifier that matches DataStreams based on their types and ids.

    Args:
        stream_type (int): The type of the stream to match
        stream_id (int): The stream identifier to match.  If None, all
            streams of the given type are matched.
        system (bool): Whether to match system or user streams.
    """

    def __init__(self, stream_type, stream_id, system):
        self.match_type = stream_type
        self.match_id = stream_id
        self.match_system = system

    @property
    def input(self):
        """Whether this is a root input stream."""

        return self.match_type == DataStream.InputType

    @property
    def buffered(self):
        return self.match_type == DataStream.BufferedType or self.match_type == DataStream.OutputType

    @classmethod
    def FromString(cls, string_rep):
        """Create a DataStreamSelector from a string.

        The format of the string should either be:

        all <type>
        OR
        <type> <id>

        Where type is [system] <stream type>, with <stream type>
        defined as in DataStream

        Args:
            rep (str): The string representation to convert to a DataStreamSelector
        """

        rep = str(string_rep)

        if rep.startswith(u'all'):
            parts = rep.split()
            if len(parts) == 3 and parts[1] == u'system':
                system = True
                stream_type = parts[2]
            elif len(parts) == 2:
                system = False
                stream_type = parts[1]
            else:
                raise ArgumentError("Invalid wildcard stream selector", string_rep=string_rep)

            try:
                stream_type = DataStream.StringToType[stream_type]
            except KeyError:
                raise ArgumentError("Invalid stream type given", stream_type=stream_type, known_types=DataStream.StringToType.keys())

            return DataStreamSelector(stream_type, None, system)

        # If we're not matching a wildcard stream type, then the match is exactly
        # the same as a DataStream identifier, so use that to match it.

        stream = DataStream.FromString(rep)
        return DataStreamSelector(stream.stream_type, stream.stream_id, stream.system)

    def __str__(self):
        type_str = DataStream.TypeToString[self.match_type]

        if self.match_id is not None:
            if self.match_system:
                return u'system {} {}'.format(type_str, self.match_id)

            return u'{} {}'.format(type_str, self.match_id)
        else:
            if self.match_system:
                return u'all system {}'.format(type_str)

            return u'all {}'.format(type_str)

    def matches(self, stream):
        """Check if this selector matches the given stream

        Args:
            stream (DataStream): The stream to check

        Returns:
            bool: True if this selector matches the stream
        """

        if self.match_type != stream.stream_type:
            return False

        if self.match_id is not None and self.match_id != stream.stream_id:
            return False

        if self.match_system != stream.system:
            return False

        return True
