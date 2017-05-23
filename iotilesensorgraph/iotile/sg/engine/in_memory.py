"""An in memory storage engine for sensor graph."""

from collections import deque
from iotile.sg import DataStream


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
        self.streaming_data = deque()
        self.storage_data = deque()

    def count(self):
        """Count the number of readings.

        Args:
            stream (DataStream): The stream to count readings in

        Returns:
            (int, int): The number of readings in storage and streaming
        """

        return (len(self.storage_data), len(self.streaming_data))

    def push(self, stream, value):
        """Store a new value for the given stream.

        Args:
            stream (DataStream): The stream to store data for
            value (IOTileReading): The value to store
        """

        if stream.stream_type == DataStream.OutputType:
            self.streaming_data.append((stream, value))
        else:
            self.streaming_data.append((stream, value))

    def pop(self, stream):
        """Remove and return the oldest value for a stream.

        Args:
            stream (DataStream): The stream to pop data from

        Returns:
            IOTileReading: The value popped from the stream
        """


