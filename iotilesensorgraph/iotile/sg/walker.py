"""Stream walkers are the basic data retrieval mechanism in sensor graph."""

from builtins import implements_iterator  # for python 3 compatibility
from iotile.core.exceptions import ArgumentError
from iotile.sg.exceptions import StreamEmptyError
from iotile.sg.stream import DataStream


class StreamWalker(object):
    """An object that walks through the SensorLog and returns matching readings.

    Args:
        selector (DataStreamSelector): The selector for the stream(s) that we
            are walking.
    """

    def __init__(self, selector):
        self.selector = selector

    def matches(self, stream):
        """Check if a stream matches this walker.

        Args:
            stream (DataStream): The stream to check
        """

        return self.selector.matches(stream)


class VirtualStreamWalker(StreamWalker):
    """A stream walker that just walks over virtual streams.

    Args:
        selector (DataStreamSelector): The selector for the stream(s) that we
            are walking.
    """

    def __init__(self, selector):
        super(VirtualStreamWalker, self).__init__(selector)

        if selector.match_id is not None:
            raise ArgumentError("You cannot create a stream walker with a wildcard virtual stream")

        self.reading = None

    def push(self, stream, value):
        """Update this stream walker with a new responsive reading.

        Virtual stream walkers keep at most one reading so this function
        just overwrites whatever was previously stored.
        """

        if not self.matches(stream):
            raise ArgumentError("Attempting to push reading to stream walker that does not match", selector=self.selector, stream=stream)

        self.reading = value

    def iter(self):
        """Iterate over the readings that are responsive to this stream walker."""

        if self.reading is not None:
            yield self.reading

    def count(self):
        if self.selector.match_type == DataStream.ConstantType:
            return 0xFFFFFFFF

        if self.reading is None:
            return 0

        return 1

    def pop(self):
        """Pop a reading off of this virtual stream and return it."""

        if self.reading is None:
            raise StreamEmptyError("Pop called on virtual stream walker without any data", selector=self.selector)

        reading = self.reading

        # If we're not a constant stream, we just exhausted ourselves
        if self.selector.match_type != DataStream.ConstantType: 
            self.reading = None

        return reading

    def peek(self):
        """Peek at the oldest reading in this virtual stream."""

        if self.reading is None:
            raise StreamEmptyError("Pop called on virtual stream walker without any data", selector=self.selector)

        return self.reading
