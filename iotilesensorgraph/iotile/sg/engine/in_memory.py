"""An in memory storage engine for sensor graph."""

from builtins import str
from iotile.sg import DataStream
from iotile.sg.exceptions import StorageFullError, StreamEmptyError


class InMemoryStorageEngine(object):
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

    def count(self):
        """Count the number of readings.

        Args:
            stream (DataStream): The stream to count readings in

        Returns:
            (int, int): The number of readings in storage and streaming
        """

        return (len(self.storage_data), len(self.streaming_data))

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

