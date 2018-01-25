"""Classes for representing and selecting data streams.

Streams are basically FIFOs with a numeric tag to represent their
identity and a series of readings.  There are two key classes:

DataStream: A wrapper around the tag that identifies the stream

DataStreamSelector: An object that selects a specific stream or a
    class of streams.
"""

# For python 2/3 compatibility using future module
from builtins import str
from future.utils import python_2_unicode_compatible, iteritems
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

    # These streams are globally important system stream codes that
    # are included by default in all wildcard stream matching.
    KnownBreakStreams = {
        1024: 'device_reboot'
    }

    def __init__(self, stream_type, stream_id, system=False):
        self.stream_type = stream_type
        self.stream_id = stream_id
        self.system = system

    @property
    def buffered(self):
        return self.stream_type == self.BufferedType or self.stream_type == self.OutputType

    @property
    def output(self):
        return self.stream_type == DataStream.OutputType

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

    @classmethod
    def FromEncoded(self, encoded):
        """Create a DataStream from an encoded 16-bit unsigned integer.

        Returns:
            DataStream: The decoded DataStream object
        """

        stream_type = (encoded >> 12) & 0b1111
        stream_system = bool(encoded & (1 << 11))
        stream_id = (encoded & ((1 << 11) - 1))

        return DataStream(stream_type, stream_id, stream_system)

    def encode(self):
        """Encode this stream as a packed 16-bit unsigned integer.

        Returns:
            int: The packed encoded stream
        """

        return (self.stream_type << 12) | (int(self.system) << 11) | self.stream_id

    def __str__(self):
        type_str = self.TypeToString[self.stream_type]

        if self.system:
            return u'system {} {}'.format(type_str, self.stream_id)

        return u'{} {}'.format(type_str, self.stream_id)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, DataStream):
            return NotImplemented

        return self.system == other.system and self.stream_type == other.stream_type and self.stream_id == other.stream_id


@python_2_unicode_compatible
class DataStreamSelector(object):
    """A specifier that matches DataStreams based on their types and ids.

    Args:
        stream_type (int): The type of the stream to match
        stream_id (int): The stream identifier to match.  If None, all
            streams of the given type are matched.
        stream_specifier (int): One of the 4 below match specifiers.
            These control whether user and/or system values are matched.
    """

    MatchSystemOnly = 1
    MatchCombined = 2
    MatchUserOnly = 3
    MatchUserAndBreaks = 4

    ValidSpecifiers = frozenset([MatchSystemOnly, MatchCombined, MatchUserOnly, MatchUserAndBreaks])

    SpecifierStrings = {
        MatchSystemOnly: u'system',
        MatchCombined: u'combined',
        MatchUserOnly: u'user',
        MatchUserAndBreaks: u''
    }

    SpecifierNames = {y: x for x, y in iteritems(SpecifierStrings)}

    SpecifierEncodings = {
        MatchSystemOnly: (1 << 11),
        MatchUserOnly: 0,
        MatchUserAndBreaks: (1 << 15),
        MatchCombined: (1 << 11) | (1 << 15)
    }

    SpecifierEncodingMap = {y: x for x, y in iteritems(SpecifierEncodings)}
    MatchAllCode = (1 << 11) - 1

    def __init__(self, stream_type, stream_id, stream_specifier):
        self.match_type = stream_type
        self.match_id = stream_id
        self.match_spec = stream_specifier

        if stream_specifier not in DataStreamSelector.ValidSpecifiers:
            raise ArgumentError("Unknown stream selector specifier", specifier=stream_specifier, known_specifiers=DataStreamSelector.ValidSpecifiers)

    @property
    def input(self):
        """Whether this is a root input stream."""

        return self.match_type == DataStream.InputType

    @property
    def inexhaustible(self):
        """Whether this is a constant stream."""

        return self.match_type == DataStream.ConstantType

    @property
    def singular(self):
        """Whether this selector matches only a single stream."""

        return self.match_id is not None

    @property
    def buffered(self):
        return self.match_type == DataStream.BufferedType or self.match_type == DataStream.OutputType

    @property
    def output(self):
        return self.match_type == DataStream.OutputType

    def as_stream(self):
        """Convert this selector to a DataStream.

        This function will only work if this is a singular selector that
        matches exactly one DataStream.
        """

        if not self.singular:
            raise ArgumentError("Attempted to convert a non-singular selector to a data stream, it matches multiple", selector=self)

        return DataStream(self.match_type, self.match_id, self.match_spec == DataStreamSelector.MatchSystemOnly)

    @classmethod
    def FromStream(cls, stream):
        """Create a DataStreamSelector from a DataStream.

        Args:
            stream (DataStream): The data stream that we want to convert.
        """

        if stream.system:
            specifier = DataStreamSelector.MatchSystemOnly
        else:
            specifier = DataStreamSelector.MatchUserOnly

        return DataStreamSelector(stream.stream_type, stream.stream_id, specifier)

    @classmethod
    def FromEncoded(cls, encoded):
        """Create a DataStreamSelector from an encoded 16-bit value.

        The binary value must be equivalent to what is produced by
        a call to self.encode() and will turn that value back into
        a a DataStreamSelector.

        Note that the following operation is a no-op:

        DataStreamSelector.FromEncode(value).encode()

        Args:
            encoded (int): The encoded binary representation of a
                DataStreamSelector.

        Returns:
            DataStreamSelector: The decoded selector.
        """

        match_spec = encoded & ((1 << 11) | (1 << 15))
        match_type = (encoded & (0b111 << 12)) >> 12
        match_id = encoded & ((1 << 11) - 1)

        if match_spec not in cls.SpecifierEncodingMap:
            raise ArgumentError("Unknown encoded match specifier", match_spec=match_spec, known_specifiers=cls.SpecifierEncodingMap.keys())

        spec_name = cls.SpecifierEncodingMap[match_spec]

        # Handle wildcard matches
        if match_id == cls.MatchAllCode:
            match_id = None

        return DataStreamSelector(match_type, match_id, spec_name)

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

        rep = rep.replace(u'node', '')
        rep = rep.replace(u'nodes', '')

        if rep.startswith(u'all'):
            parts = rep.split()

            spec_string = u''

            if len(parts) == 3:
                spec_string = parts[1]
                stream_type = parts[2]
            elif len(parts) == 2:
                stream_type = parts[1]
            else:
                raise ArgumentError("Invalid wildcard stream selector", string_rep=string_rep)

            try:
                # Remove pluralization that can come with e.g. 'all system outputs'
                if stream_type.endswith(u's'):
                    stream_type = stream_type[:-1]

                stream_type = DataStream.StringToType[stream_type]
            except KeyError:
                raise ArgumentError("Invalid stream type given", stream_type=stream_type, known_types=DataStream.StringToType.keys())

            stream_spec = DataStreamSelector.SpecifierNames.get(spec_string, None)
            if stream_spec is None:
                raise ArgumentError("Invalid stream specifier given (should be system, user, combined or blank)", string_rep=string_rep, spec_string=spec_string)

            return DataStreamSelector(stream_type, None, stream_spec)

        # If we're not matching a wildcard stream type, then the match is exactly
        # the same as a DataStream identifier, so use that to match it.

        stream = DataStream.FromString(rep)
        return DataStreamSelector.FromStream(stream)

    def __str__(self):
        type_str = DataStream.TypeToString[self.match_type]

        if self.match_id is not None:
            if self.match_spec == DataStreamSelector.MatchSystemOnly:
                return u'system {} {}'.format(type_str, self.match_id)

            return u'{} {}'.format(type_str, self.match_id)
        else:
            specifier = DataStreamSelector.SpecifierStrings[self.match_spec]

            if specifier != u'':
                specifier += u' '

            if type_str != u'buffered':
                type_str = type_str + 's'

            return u'all {}{}'.format(specifier, type_str)

    def matches(self, stream):
        """Check if this selector matches the given stream

        Args:
            stream (DataStream): The stream to check

        Returns:
            bool: True if this selector matches the stream
        """

        if self.match_type != stream.stream_type:
            return False

        if self.match_id is not None:
            return self.match_id == stream.stream_id

        if self.match_spec == DataStreamSelector.MatchUserOnly:
            return not stream.system
        elif self.match_spec == DataStreamSelector.MatchSystemOnly:
            return stream.system
        elif self.match_spec == DataStreamSelector.MatchUserAndBreaks:
            return (not stream.system) or (stream.system and (stream.stream_id in DataStream.KnownBreakStreams))

        # The other case is that match_spec is MatchCombined, which matches everything
        # regardless of system of user flag
        return True

    def encode(self):
        """Encode this stream as a packed 16-bit unsigned integer.

        Returns:
            int: The packed encoded stream
        """

        match_id = self.match_id
        if match_id is None:
            match_id = (1 << 11) - 1

        return (self.match_type << 12) | DataStreamSelector.SpecifierEncodings[self.match_spec] | match_id

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, DataStreamSelector):
            return NotImplemented

        return self.match_spec == other.match_spec and self.match_type == other.match_type and self.match_id == other.match_id
