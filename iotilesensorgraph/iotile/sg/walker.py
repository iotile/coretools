"""Stream walkers are the basic data retrieval mechanism in sensor graph."""

from iotile.core.exceptions import ArgumentError, InternalError
from iotile.sg.exceptions import StreamEmptyError
from iotile.sg.stream import DataStream


class StreamWalker(object):
    """An object that walks through the SensorLog and returns matching readings.

    Args:
        selector (DataStreamSelector): The selector for the stream(s) that we
            are walking.

    Returns:
        bool: Whether the walker matches the stream
    """

    def __init__(self, selector):
        self.selector = selector

    def matches(self, stream):
        """Check if a stream matches this walker.

        Args:
            stream (DataStream): The stream to check
        """

        return self.selector.matches(stream)

    @property
    def buffered(self):
        return self.selector.buffered


class BufferedStreamWalker(StreamWalker):
    """A stream walker backed by a storage buffer.

    Args:
        selector (DataStreamSelector): The selector for the streams
            that we are walking
        engine (StorageEngine): The storage engine backing us up
    """

    def __init__(self, selector, engine):
        super(BufferedStreamWalker, self).__init__(selector)
        self.engine = engine
        self._count = 0

        storage, streaming = self.engine.count()

        if selector.output:
            self.offset = streaming
            self.storage_type = u'streaming'
        else:
            self.offset = storage
            self.storage_type = u'storage'

    def count(self):
        return self._count

    def pop(self):
        """Pop a reading off of this stream and return it."""

        if self._count == 0:
            raise StreamEmptyError("Pop called on buffered stream walker without any data", selector=self.selector)

        while True:
            curr = self.engine.get(self.storage_type, self.offset)
            self.offset += 1

            stream = DataStream.FromEncoded(curr.stream)
            if self.matches(stream):
                self._count -= 1
                return curr

    def peek(self):
        """Peek at the oldest reading in this virtual stream."""

        if self._count == 0:
            raise StreamEmptyError("Peek called on buffered stream walker without any data", selector=self.selector)

        offset = self.offset

        while True:
            curr = self.engine.get(self.storage_type, offset)
            offset += 1

            stream = DataStream.FromEncoded(curr.stream)
            if self.matches(stream):
                return curr

    def skip_all(self):
        """Skip all readings in this walker."""

        storage, streaming = self.engine.count()

        if self.selector.output:
            self.offset = streaming
        else:
            self.offset = storage

        self._count = 0

    def notify_added(self, stream):
        """Notify that a new reading has been added.

        Args:
            stream (DataStream): The stream that had new data
        """

        if not self.matches(stream):
            return

        self._count += 1

    def notify_rollover(self, stream):
        """Notify that a reading in the given stream was overwritten.

        Args:
            stream (DataStream): The stream that had overwritten data.
        """

        self.offset -= 1

        if not self.matches(stream):
            return

        if self._count == 0:
            raise InternalError("BufferedStreamWalker out of sync with storage engine, count was wrong.")

        self._count -= 1


class VirtualStreamWalker(StreamWalker):
    """A stream walker that just walks over virtual streams.

    Args:
        selector (DataStreamSelector): The selector for the stream(s) that we
            are walking.
    """

    def __init__(self, selector):
        super(VirtualStreamWalker, self).__init__(selector)

        if selector.match_id is None:
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

    def skip_all(self):
        """Skip all readings in this walker."""

        # We can't skip a constant stream
        if self.selector.match_type == DataStream.ConstantType:
            return

        self.reading = None


class CounterStreamWalker(StreamWalker):
    """A stream walker that walks across a counter stream.

    Counter streams only store one reading but keep an accurate
    count of how many times they've been pushed and popped and
    return the last value pushed for each each pop until they're
    empty.

    Args:
        selector (DataStreamSelector): The selector for the stream(s) that
            we're supposed to walk.
    """

    def __init__(self, selector):
        super(CounterStreamWalker, self).__init__(selector)

        if selector.match_id is None:
            raise ArgumentError("You cannot create a stream walker with a wildcard virtual stream")

        self.reading = None
        self._count = 0

    def push(self, stream, value):
        """Update this stream walker with a new responsive reading.

        Args:
            stream (DataStream): The stream that we're pushing
            value (IOTileReading): The reading tha we're pushing
        """

        if not self.matches(stream):
            raise ArgumentError("Attempting to push reading to stream walker that does not match", selector=self.selector, stream=stream)

        self.reading = value
        self._count += 1

    def iter(self):
        """Iterate over the readings that are responsive to this stream walker."""

        for i in xrange(0, self._count):
            yield self.reading

    def count(self):
        """Count how many readings are available in this walker."""

        return self._count

    def pop(self):
        """Pop a reading off of this virtual stream and return it."""

        if self._count == 0:
            raise StreamEmptyError("Pop called on virtual stream walker without any data", selector=self.selector)

        self._count = self._count - 1
        return self.reading

    def peek(self):
        """Peek at the oldest reading in this virtual stream."""

        if self.reading is None:
            raise StreamEmptyError("peek called on virtual stream walker without any data", selector=self.selector)

        return self.reading

    def skip_all(self):
        """Skip all readings in this walker."""

        self._count = 0


class InvalidStreamWalker(StreamWalker):
    """A stream walker that is not connected to anything.

    These stream walkers are cannot be used to hold any data and always
    have a count() of 0 but they are useful for unconnected inputs on
    sensor graph node.  The only functions that work are:

        skip_all
        count

    Args:
        selector (DataStreamSelector): The selector for the stream(s) that
            we're supposed to walk.
    """

    def __init__(self, selector):
        super(InvalidStreamWalker, self).__init__(selector)

    def matches(self, stream):
        """Check if a stream matches this walker.

        Args:
            stream (DataStream): The stream to check

        Returns:
            bool: Whether the walker matches the stream
        """

        return False

    def push(self, stream, value):
        """Update this stream walker with a new responsive reading.

        Args:
            stream (DataStream): The stream that we're pushing
            value (IOTileReading): The reading tha we're pushing
        """

        raise ArgumentError("Attempting to push reading to an invalid stream walker that cannot hold data", selector=self.selector, stream=stream)


    def iter(self):
        """Iterate over the readings that are responsive to this stream walker."""

        return []

    def count(self):
        """Count how many readings are available in this walker."""

        return 0

    def pop(self):
        """Pop a reading off of this virtual stream and return it."""

        raise StreamEmptyError("Pop called on an invalid stream walker")

    def peek(self):
        """Peek at the oldest reading in this virtual stream."""

        raise StreamEmptyError("peek called on an invalid stream walker")

    def skip_all(self):
        """Skip all readings in this walker."""

        pass
