"""An in memory storage engine for sensor graph."""

from iotile.core.exceptions import ArgumentError
from iotile.core.hw.reports import IOTileReading
from iotile.sg import DataStream
from iotile.sg.exceptions import StorageFullError, StreamEmptyError


class InMemoryStorageEngine:
    """A simple in memory storage engine for sensor graph.

    Args:
        model (DeviceModel): A model for the device type that we are
            emulating so that we can constrain our total memory
            size appropriately to get the same behavior that would
            be seen on an actual device.
    """

    def __init__(self, model):
        self.model = model
        self.storage_length = model.get(u'max_storage_buffer')
        self.streaming_length = model.get(u'max_streaming_buffer')
        self.streaming_data = []
        self.storage_data = []

    def dump(self):
        """Serialize the state of this InMemoryStorageEngine to a dict.

        Returns:
            dict: The serialized data.
        """

        return {
            u'storage_data': [x.asdict() for x in self.storage_data],
            u'streaming_data': [x.asdict() for x in self.streaming_data]
        }

    def restore(self, state):
        """Restore the state of this InMemoryStorageEngine from a dict."""

        storage_data = state.get(u'storage_data', [])
        streaming_data = state.get(u'streaming_data', [])

        if len(storage_data) > self.storage_length or len(streaming_data) > self.streaming_length:
            raise ArgumentError("Cannot restore InMemoryStorageEngine, too many readings",
                                storage_size=len(storage_data), storage_max=self.storage_length,
                                streaming_size=len(streaming_data), streaming_max=self.streaming_length)

        self.storage_data = [IOTileReading.FromDict(x) for x in storage_data]
        self.streaming_data = [IOTileReading.FromDict(x) for x in streaming_data]

    def count(self):
        """Count the number of readings.

        Returns:
            (int, int): The number of readings in storage and streaming buffers.
        """

        return (len(self.storage_data), len(self.streaming_data))

    def count_matching(self, selector, offset=0):
        """Count the number of readings matching selector.

        Args:
            selector (DataStreamSelector): The selector that we want to
                count matching readings for.
            offset (int): The starting offset that we should begin counting at.

        Returns:
            int: The number of matching readings.
        """

        if selector.output:
            data = self.streaming_data
        elif selector.buffered:
            data = self.storage_data
        else:
            raise ArgumentError("You can only pass a buffered selector to count_matching", selector=selector)

        count = 0
        for i in range(offset, len(data)):
            reading = data[i]

            stream = DataStream.FromEncoded(reading.stream)
            if selector.matches(stream):
                count += 1

        return count

    def scan_storage(self, area_name, callable, start=0, stop=None):
        """Iterate over streaming or storage areas, calling callable.

        Args:
            area_name (str): Either 'storage' or 'streaming' to indicate which
                storage area to scan.
            callable (callable): A function that will be called as (offset, reading)
                for each reading between start_offset and end_offset (inclusive).  If
                the scan function wants to stop early it can return True.  If it returns
                anything else (including False or None), scanning will continue.
            start (int): Optional offset to start at (included in scan).
            stop (int): Optional offset to end at (included in scan).

        Returns:
            int: The number of entries scanned.
        """

        if area_name == u'storage':
            data = self.storage_data
        elif area_name == u'streaming':
            data = self.streaming_data
        else:
            raise ArgumentError("Unknown area name in scan_storage (%s) should be storage or streaming" % area_name)

        if len(data) == 0:
            return 0

        if stop is None:
            stop = len(data) - 1
        elif stop >= len(data):
            raise ArgumentError("Given stop offset is greater than the highest offset supported", length=len(data), stop_offset=stop)

        scanned = 0
        for i in range(start, stop + 1):
            scanned += 1

            should_break = callable(i, data[i])
            if should_break is True:
                break

        return scanned

    def clear(self):
        """Clear all data from this storage engine."""

        self.storage_data = []
        self.streaming_data = []

    def push(self, value):
        """Store a new value for the given stream.

        Args:
            value (IOTileReading): The value to store.  The stream
                parameter must have the correct value
        """

        stream = DataStream.FromEncoded(value.stream)

        if stream.stream_type == DataStream.OutputType:
            if len(self.streaming_data) == self.streaming_length:
                raise StorageFullError('Streaming buffer full')

            self.streaming_data.append(value)
        else:
            if len(self.storage_data) == self.storage_length:
                raise StorageFullError('Storage buffer full')

            self.storage_data.append(value)

    def get(self, buffer_type, offset):
        """Get a reading from the buffer at offset.

        Offset is specified relative to the start of the data buffer.
        This means that if the buffer rolls over, the offset for a given
        item will appear to change.  Anyone holding an offset outside of this
        engine object will need to be notified when rollovers happen (i.e.
        popn is called so that they can update their offset indices)

        Args:
            buffer_type (str): The buffer to pop from (either u"storage" or u"streaming")
            offset (int): The offset of the reading to get
        """

        if buffer_type == u'streaming':
            chosen_buffer = self.streaming_data
        else:
            chosen_buffer = self.storage_data

        if offset >= len(chosen_buffer):
            raise StreamEmptyError("Invalid index given in get command", requested=offset, stored=len(chosen_buffer), buffer=buffer_type)

        return chosen_buffer[offset]

    def popn(self, buffer_type, count):
        """Remove and return the oldest count values from the named buffer

        Args:
            buffer_type (str): The buffer to pop from (either u"storage" or u"streaming")
            count (int): The number of readings to pop

        Returns:
            list(IOTileReading): The values popped from the buffer
        """

        buffer_type = str(buffer_type)

        if buffer_type == u'streaming':
            chosen_buffer = self.streaming_data
        else:
            chosen_buffer = self.storage_data

        if count > len(chosen_buffer):
            raise StreamEmptyError("Not enough data in buffer for popn command", requested=count, stored=len(chosen_buffer), buffer=buffer_type)

        popped = chosen_buffer[:count]
        remaining = chosen_buffer[count:]

        if buffer_type == u'streaming':
            self.streaming_data = remaining
        else:
            self.storage_data = remaining

        return popped
