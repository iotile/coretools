"""A centralized data management structure that allows multiple named FIFO streams.

SensorGraph is organized around data streams, which are named FIFOs that hold
readings.  For the purposes of embedding SensorGraph into a low resource setting
you can limit the number of readings stored in any given FIFO as needed to put
a hard cap on storage requirements.
"""

import copy
from future.utils import viewitems
from iotile.sg.model import DeviceModel
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.reports import IOTileReading
from .engine import InMemoryStorageEngine
from .stream import DataStream, DataStreamSelector
from .walker import VirtualStreamWalker, CounterStreamWalker, BufferedStreamWalker
from .exceptions import StreamEmptyError, StorageFullError, UnresolvedIdentifierError


class SensorLog(object):
    """A storage engine holding multiple named FIFOs.

    Normally a SensorLog is used in ring-buffer mode which means that old
    readings are automatically overwritten as needed when new data is saved.

    However, you can configure it into fill-stop mode by using:
    set_rollover("streaming"|"storage", True|False)

    By default rollover is set to True for both streaming and storage and can
    be controlled individually for each one.

    Readings that are committed to persistent storage streams are assigned
    unique identifiers.  If you have an external system for setting reading
    ids, you can send them to push() already assigned with correct reading
    ids.  If you would prefer to have SensorLog assign the IDs for you, you
    can do so by setting the id_assigner parameter to a callable that will be
    called with the stream and reading and should return an integer.

    Args:
        engine (StorageEngine): The engine used for storing persistent data
            generated by this sensor graph. This can either be a simple, in
            memory data store, or a more complicated persistent storage setup
            depending on needs.  If not specified, a temporary in memory
            engine is used.
        model (DeviceModel): An optional device model specifying the
            constraints of the device that we are emulating.  If not
            specified, no specific constraints are imposed on the sensor log.
        id_assigner (callable): Optional callable function that will be used
            to assign the reading_id to each IOTileReading that is committed
            to persistent storage.  You can also set this later by using the
            id_assigner property.  If you do not specify this parameter or
            set it later, then it will be assumed that the readings sent
            to push() already have correct reading_id numbers.
    """

    def __init__(self, engine=None, model=None, id_assigner=None):
        self._monitors = {}
        self._last_values = {}
        self._virtual_walkers = []
        self._queue_walkers = []

        if model is None:
            model = DeviceModel()

        if engine is None:
            engine = InMemoryStorageEngine(model=model)

        self._engine = engine
        self._model = model
        self._rollover_streaming = True
        self._rollover_storage = True

        self.id_assigner = id_assigner

    def dump(self):
        """Dump the state of this SensorLog.

        The purpose of this method is to be able to restore the same state
        later.  However there are links in the SensorLog for stream walkers.

        So the dump process saves the state of each stream walker and upon
        restore, it looks through the current set of stream walkers and
        restores each one that existed when dump() was called to its state.

        Returns:
            dict: The serialized state of this SensorLog.
        """

        walkers = {}
        walkers.update({str(walker.selector): walker.dump() for walker in self._queue_walkers})
        walkers.update({str(walker.selector): walker.dump() for walker in self._virtual_walkers})

        return {
            u'engine': self._engine.dump(),
            u'rollover_storage': self._rollover_storage,
            u'rollover_streaming': self._rollover_streaming,
            u'last_values': {str(stream): reading.asdict() for stream, reading in viewitems(self._last_values)},
            u'walkers': walkers
        }

    def restore(self, state, permissive=False):
        """Restore a state previously dumped by a call to dump().

        The purpose of this method is to be able to restore a previously
        dumped state.  However there are links in the SensorLog for stream
        walkers.

        So the restore process looks through the current set of stream walkers
        and restores each one that existed when dump() was called to its
        state.  If there are walkers allocated that were not present when
        dump() was called, an exception is raised unless permissive=True,
        in which case they are ignored.

        Args:
            state (dict): The previous state to restore, from a prior call
                to dump().
            permissive (bool): Whether to raise an exception is new stream
                walkers are present that do not have dumped contents().

        Raises:
            ArgumentError: There are new stream walkers present in the current
                SensorLog and permissive==False.
        """

        self._engine.restore(state.get(u'engine'))
        self._last_values = {DataStream.FromString(stream): IOTileReading.FromDict(reading) for
                             stream, reading in viewitems(state.get(u"last_values", {}))}

        self._rollover_storage = state.get(u'rollover_storage', True)
        self._rollover_streaming = state.get(u'rollover_streaming', True)

        old_walkers = {DataStreamSelector.FromString(selector): dump for selector, dump in
                       viewitems(state.get(u"walkers"))}

        for walker in self._virtual_walkers:
            if walker.selector in old_walkers:
                walker.restore(old_walkers[walker.selector])
            elif not permissive:
                raise ArgumentError("Cannot restore SensorLog, walker %s exists in restored log but did not exist before" % str(walker.selector))

        for walker in self._queue_walkers:
            if walker.selector in old_walkers:
                walker.restore(old_walkers[walker.selector])
            elif not permissive:
                raise ArgumentError("Cannot restore SensorLog, walker %s exists in restored log but did not exist before" % str(walker.selector))

    def set_rollover(self, area, enabled):
        """Configure whether rollover is enabled for streaming or storage streams.

        Normally a SensorLog is used in ring-buffer mode which means that old
        readings are automatically overwritten as needed when new data is saved.

        However, you can configure it into fill-stop mode by using:
        set_rollover("streaming"|"storage", True|False)

        By default rollover is set to True for both streaming and storage and can
        be controlled individually for each one.

        Args:
            area (str): Either streaming or storage.
            enabled (bool): Whether to enable or disable rollover.
        """

        if area == u'streaming':
            self._rollover_streaming = enabled
        elif area == u'storage':
            self._rollover_storage = enabled
        else:
            raise ArgumentError("You must pass one of 'storage' or 'streaming' to set_rollover", area=area)

    def dump_constants(self):
        """Dump (stream, value) pairs for all constant streams.

        This method walks the internal list of defined stream walkers and
        dumps the current value for all constant streams.

        Returns:
            list of (DataStream, IOTileReading): A list of all of the defined constants.
        """

        constants = []

        for walker in self._virtual_walkers:
            if not walker.selector.inexhaustible:
                continue

            constants.append((walker.selector.as_stream(), walker.reading))

        return constants

    def watch(self, selector, callback):
        """Call a function whenever a stream changes.

        Args:
            selector (DataStreamSelector): The selector to watch.
                If this is None, it is treated as a wildcard selector
                that matches every stream.
            callback (callable): The function to call when a new
                reading is pushed.  Callback is called as:
                callback(stream, value)
        """

        if selector not in self._monitors:
            self._monitors[selector] = set()

        self._monitors[selector].add(callback)

    def create_walker(self, selector, skip_all=True):
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
            skip_all (bool): Whether to start at the beginning of the data
                or to skip everything and start at the end.  Defaults
                to skipping everything.  This parameter only has any
                effect on buffered stream selectors.

        Returns:
            StreamWalker: A properly updating stream walker with the given selector.
        """

        if selector.buffered:
            walker = BufferedStreamWalker(selector, self._engine, skip_all=skip_all)
            self._queue_walkers.append(walker)
            return walker

        if selector.match_type == DataStream.CounterType:
            walker = CounterStreamWalker(selector)
        else:
            walker = VirtualStreamWalker(selector)

        self._virtual_walkers.append(walker)

        return walker

    def destroy_walker(self, walker):
        """Destroy a previously created stream walker.

        Args:
            walker (StreamWalker): The walker to remove from internal updating
                lists.
        """

        if walker.buffered:
            self._queue_walkers.remove(walker)
        else:
            self._virtual_walkers.remove(walker)

    def restore_walker(self, dumped_state):
        """Restore a stream walker that was previously serialized.

        Since stream walkers need to be tracked in an internal list for
        notification purposes, we need to be careful with how we restore
        them to make sure they remain part of the right list.

        Args:
            dumped_state (dict): The dumped state of a stream walker
                from a previous call to StreamWalker.dump()

        Returns:
            StreamWalker: The correctly restored StreamWalker subclass.
        """

        selector_string = dumped_state.get(u'selector')
        if selector_string is None:
            raise ArgumentError("Invalid stream walker state in restore_walker, missing 'selector' key", state=dumped_state)

        selector = DataStreamSelector.FromString(selector_string)

        walker = self.create_walker(selector)
        walker.restore(dumped_state)
        return walker

    def destroy_all_walkers(self):
        """Destroy any previously created stream walkers."""

        self._queue_walkers = []
        self._virtual_walkers = []

    def count(self):
        """Count many many readings are persistently stored.

        Returns:
            (int, int): The number of readings in storage and output areas.
        """

        return self._engine.count()

    def clear(self):
        """Clear all data from this sensor_log.

        All readings in all walkers are skipped and buffered data is
        destroyed.
        """

        for walker in self._virtual_walkers:
            walker.skip_all()

        self._engine.clear()

        for walker in self._queue_walkers:
            walker.skip_all()

        self._last_values = {}

    def push(self, stream, reading):
        """Push a reading into a stream, updating any associated stream walkers.

        Args:
            stream (DataStream): the stream to push the reading into
            reading (IOTileReading): the reading to push
        """

        # Make sure the stream is correct
        reading = copy.copy(reading)
        reading.stream = stream.encode()

        if stream.buffered:
            output_buffer = stream.output

            if self.id_assigner is not None:
                reading.reading_id = self.id_assigner(stream, reading)

            try:
                self._engine.push(reading)
            except StorageFullError:
                # If we are in fill-stop mode, don't auto erase old data.
                if (stream.output and not self._rollover_streaming) or (not stream.output and not self._rollover_storage):
                    raise

                self._erase_buffer(stream.output)
                self._engine.push(reading)

            for walker in self._queue_walkers:
                # Only notify the walkers that are on this queue
                if walker.selector.output == output_buffer:
                    walker.notify_added(stream)

        # Activate any monitors we have for this stream
        for selector in self._monitors:
            if selector is None or selector.matches(stream):
                for callback in self._monitors[selector]:
                    callback(stream, reading)

        # Virtual streams live only in their walkers, so update each walker
        # that contains this stream.
        for walker in self._virtual_walkers:
            if walker.matches(stream):
                walker.push(stream, reading)

        self._last_values[stream] = reading

    def _erase_buffer(self, output_buffer):
        """Erase readings in the specified buffer to make space."""

        erase_size = self._model.get(u'buffer_erase_size')

        buffer_type = u'storage'
        if output_buffer:
            buffer_type = u'streaming'

        old_readings = self._engine.popn(buffer_type, erase_size)

        # Now go through all of our walkers that could match and
        # update their availability counts and data buffer pointers
        for reading in old_readings:
            stream = DataStream.FromEncoded(reading.stream)

            for walker in self._queue_walkers:
                # Only notify the walkers that are on this queue
                if walker.selector.output == output_buffer:
                    walker.notify_rollover(stream)

    def inspect_last(self, stream, only_allocated=False):
        """Return the last value pushed into a stream.

        This function works even if the stream is virtual and no
        virtual walker has been created for it.  It is primarily
        useful to aid in debugging sensor graphs.

        Args:
            stream (DataStream): The stream to inspect.
            only_allocated (bool): Optional parameter to only allow inspection
                of allocated virtual streams.  This is useful for mimicking the
                behavior of an embedded device that does not have a _last_values
                array.

        Returns:
            IOTileReading: The data in the stream

        Raises:
            StreamEmptyError: if there has never been data written to
                the stream.
            UnresolvedIdentifierError: if only_allocated is True and there has not
                been a virtual stream walker allocated to listen to this stream.
        """

        if only_allocated:
            found = False
            for walker in self._virtual_walkers:
                if walker.matches(stream):
                    found = True
                    break

            if not found:
                raise UnresolvedIdentifierError("inspect_last could not find an allocated virtual streamer for the desired stream", stream=stream)

        if stream in self._last_values:
            return self._last_values[stream]

        raise StreamEmptyError(u"inspect_last called on stream that has never been written to", stream=stream)
