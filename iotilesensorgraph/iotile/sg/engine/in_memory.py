"""An in memory storage engine for sensor graph."""


class InMemoryStorageEngine(object):
    """A simple in memory storage engine for sensor graph.

    Args:
        model (DeviceModel): A model for the device type that we are
            emulating so that we can constrain our total memory
            size appropriately to get the same behavior that would
            be seen on an actual device.
    """

    def __init__(self, model):
        self.persistent = []
        self.virtual_streams = {}
        self.model = model

    def count(self, stream):
        """Count the number of readings in a stream.

        Args:
            stream (DataStream): The stream to count readings in

        Returns:
            int: The number of readings stored for this stream.
        """

    def push(self, stream, value):
        """Store a new value for the given stream.

        Args:
            stream (DataStream): The stream to store data for
            value (IOTileReading): The value to store
        """

    def pop(self, stream):
        """Remove and return the oldest value for a stream.

        Args:
            stream (DataStream): The stream to pop data from

        Returns:
            IOTileReading: The value popped from the stream
        """


