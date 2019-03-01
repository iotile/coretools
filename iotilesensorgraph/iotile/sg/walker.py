"""Stream walkers are the basic data retrieval mechanism in sensor graph."""

from iotile.core.exceptions import ArgumentError, InternalError
from iotile.core.hw.reports import IOTileReading
from iotile.sg.exceptions import StreamEmptyError, UnresolvedIdentifierError
from iotile.sg.stream import DataStream, DataStreamSelector


class StreamWalker:
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

        Returns:
            bool: True if there is match, otherwise False
        """

        return self.selector.matches(stream)

    @property
    def buffered(self):
        """Whether this stream walker is backed by actual persistent storage (True)."""

        return self.selector.buffered


class BufferedStreamWalker(StreamWalker):
    """A stream walker backed by a storage buffer.

    Args:
        selector (DataStreamSelector): The selector for the streams
            that we are walking
        engine (StorageEngine): The storage engine backing us up
        skip_all (bool): Whether to start at the beginning of the data
            or to skip everything and start at the end.  Defaults
            to skipping everything.
    """

    def __init__(self, selector, engine, skip_all=True):
        super(BufferedStreamWalker, self).__init__(selector)
        self.engine = engine

        storage, streaming = self.engine.count()

        self._count = 0
        self.offset = 0
        if not skip_all:
            self._count = engine.count_matching(selector)

        if selector.output:
            if skip_all:
                self.offset = streaming

            self.storage_type = u'streaming'
        else:
            if skip_all:
                self.offset = storage

            self.storage_type = u'storage'

    def dump(self):
        """Dump the state of this stream walker.

        Returns:
            dict: The serialized state.
        """

        return {
            u'selector': str(self.selector),
            u'offset': self.offset
        }

    def restore(self, state):
        """Restore a previous state of this stream walker.

        Raises:
            ArgumentError: If the state refers to a different selector or the
                offset is invalid.
        """

        selector = DataStreamSelector.FromString(state.get(u'selector'))
        if selector != self.selector:
            raise ArgumentError("Attempted to restore a BufferedStreamWalker with a different selector",
                                selector=self.selector, serialized_data=state)

        self.seek(state.get(u'offset'), target="offset")

    def count(self):
        """Return the count of available readings in this stream walker."""

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

    def seek(self, value, target="offset"):
        """Seek this stream to a specific offset or reading id.

        There are two modes of use.  You can seek to a specific reading id,
        which means the walker will be positioned exactly at the reading
        pointed to by the reading ID.  If the reading id cannot be found
        an exception will be raised.  The reading id can be found but corresponds
        to a reading that is not selected by this walker, the walker will
        be moved to point at the first reading after that reading and False
        will be returned.

        If target=="offset", the walker will be positioned at the specified
        offset in the sensor log. It will also update the count of available
        readings based on that new location so that the count remains correct.

        The offset does not need to correspond to a reading selected by this
        walker.  If offset does not point to a selected reading, the effective
        behavior will be as if the walker pointed to the next selected reading
        after `offset`.

        Args:
            value (int): The identifier to seek, either an offset or a
                reading id.
            target (str): The type of thing to seek.  Can be offset or id.
                If id is given, then a reading with the given ID will be
                searched for.  If offset is given then the walker will
                be positioned at the given offset.

        Returns:
            bool: True if an exact match was found, False otherwise.

            An exact match means that the offset or reading ID existed and
            corresponded to a reading selected by this walker.

            An inexact match means that the offset or reading ID existed but
            corresponded to reading that was not selected by this walker.

            If the offset or reading ID could not be found an Exception is
            thrown instead.

        Raises:
            ArgumentError: target is an invalid string, must be offset or
                id.
            UnresolvedIdentifierError: the desired offset or reading id
                could not be found.
        """

        if target not in (u'offset', u'id'):
            raise ArgumentError("You must specify target as either offset or id", target=target)

        if target == u'offset':
            self._verify_offset(value)
            self.offset = value
        else:
            self.offset = self._find_id(value)

        self._count = self.engine.count_matching(self.selector, offset=self.offset)

        curr = self.engine.get(self.storage_type, self.offset)
        return self.matches(DataStream.FromEncoded(curr.stream))

    def _find_id(self, reading_id):
        shared = [None]

        def _id_searcher(i, reading):
            """Find the offset of the first reading with the given reading id."""
            if reading.reading_id == reading_id:
                shared[0] = i
                return True

            return False

        self.engine.scan_storage(self.storage_type, _id_searcher)
        found_offset = shared[0]

        if found_offset is None:
            raise UnresolvedIdentifierError("Cannot find reading ID '%d' in storage area '%s'" % (reading_id, self.storage_type))

        return found_offset

    def _verify_offset(self, offset):
        storage_count, streaming_count = self.engine.count()

        if self.storage_type == u'streaming':
            count = streaming_count
        else:
            count = storage_count

        if offset >= count:
            raise UnresolvedIdentifierError("Invalid offset that is larger than the number of valid readings", count=count, offset=offset)
        self.offset = offset

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

    def dump(self):
        """Serialize the state of this stream walker.

        Returns:
            dict: The serialized state.
        """

        reading = self.reading
        if reading is not None:
            reading = reading.asdict()

        return {
            u'selector': str(self.selector),
            u'reading': reading
        }

    def restore(self, state):
        """Restore the contents of this virtual stream walker.

        Args:
            state (dict): The previously serialized state.

        Raises:
            ArgumentError: If the serialized state does not have
                a matching selector.
        """

        reading = state.get(u'reading')
        if reading is not None:
            reading = IOTileReading.FromDict(reading)

        selector = DataStreamSelector.FromString(state.get(u'selector'))
        if self.selector != selector:
            raise ArgumentError("Attempted to restore a VirtualStreamWalker with a different selector",
                                selector=self.selector, serialized_data=state)

        self.reading = reading

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

    def dump(self):
        """Serialize the state of this stream walker.

        Returns:
            dict: The serialized state.
        """

        reading = self.reading
        if reading is not None:
            reading = reading.asdict()

        return {
            u'selector': str(self.selector),
            u'reading': reading,
            u'count': self._count
        }

    def restore(self, state):
        """Restore the contents of this counter stream walker.

        Args:
            state (dict): The previously serialized state.

        Raises:
            ArgumentError: If the serialized state does not have
                a matching selector.
        """

        reading = state.get(u'reading')
        if reading is not None:
            reading = IOTileReading.FromDict(reading)

        selector = DataStreamSelector.FromString(state.get(u'selector'))
        if self.selector != selector:
            raise ArgumentError("Attempted to restore a CounterStreamWalker with a different selector",
                                selector=self.selector, serialized_data=state)

        count = state.get(u'count')

        self.reading = reading
        self._count = count

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

        for _i in range(0, self._count):
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

    def dump(self):
        """Serialize the state of this stream walker.

        Returns:
            dict: The serialized state.
        """

        return {
            u'selector': str(self.selector),
            u'type': u"invalid"
        }

    def restore(self, state):
        """Restore the contents of this virtual stream walker.

        Args:
            state (dict): The previously serialized state.

        Raises:
            ArgumentError: If the serialized state does not have
                a matching selector.
        """


        selector = DataStreamSelector.FromString(state.get(u'selector'))
        if self.selector != selector:
            raise ArgumentError("Attempted to restore an InvalidStreamWalker with a different selector",
                                selector=self.selector, serialized_data=state)

        if state.get(u'type') != u'invalid':
            raise ArgumentError("Invalid serialized state for InvalidStreamWalker", serialized_data=state)

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
