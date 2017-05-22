"""A centralized data management structure that allows multiple named FIFO streams.

SensorGraph is organized around data streams, which are named FIFOs that hold
readings.  For the purposes of embedding SensorGraph into a low resource setting
you can limit the number of readings stored in any given FIFO as needed to put
a hard cap on storage requirements.
"""

from .engine import InMemoryStorageEngine
from .stream import DataStreamSelector
from .walker import VirtualStreamWalker
from .exceptions import StreamEmptyError
from iotile.core.exceptions import ArgumentError


class SensorLog(object):
    """A storage engine holding multiple named FIFOs.

    Args:
        engine (StorageEngine): The engine used for storing
            persistent data generated by this sensor graph.
            This can either be a simple, in memory data store, or
            a more complicated persistent storage setup depending on
            needs.  If not specified, a temporary in memory engine
            is used.

        model (DeviceModel): An optional device model specifying the
            constraints of the device that we are emulating.  If not
            specified, no specific constraints are imposed on the sensor
            log.
    """

    def __init__(self, engine=None, model=None):
        self._monitors = {}
        self._virtual_walkers = []
        self._queue_walkers = []

        if engine is None:
            engine = InMemoryStorageEngine(model=model)

        self._engine = engine
        self._model = model

    def create_walker(self, selector):
        """Create a stream walker based on the given selector.

        This function returns a StreamWalker subclass that will 
        remain up to date and allow iterating over and popping readings
        from the stream(s) specified by the selector.  

        When the stream walker is done, it should be passed to 
        destroy_walker so that it is removed from internal lists that
        are used to always keep it in sync.

        Args:
            selector (DataStreamSelector): The selector describing the
                streams that we want to iterate over.
        """

        if selector.buffered:
            raise ArgumentError("Buffered stream walkers are not yet supported")

        walker = VirtualStreamWalker(selector)
        self._virtual_walkers.append(walker)

        return walker

    def destroy_walkers(self, walker):
        """Destroy a previously created stream walker.

        Args:
            walker (StreamWalker): The walker to remove from internal updating
                lists.
        """

        if walker.buffered:
            self._queue_walkers.remove(walker)
        else:
            self._virtual_walkers.remove(walker)

    def push(self, stream, reading):
        """Push a reading into a stream, updating any associated stream walkers.

        Args:
            stream (DataStream): the stream to push the reading into
            reading (IOTileReading): the reading to push
        """

        if stream.buffered:
            raise ArgumentError("Buffered readings are not yet supported")

        # Virtual streams live only in their walkers, so update each walker
        # that contains this stream.
        for walker in self._virtual_walkers:
            if walker.matches(stream):
                walker.push(stream, reading)
