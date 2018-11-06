"""Mixin for the raw sensor log.

The raw sensor log is the subsystem that stores sensor readings
on behalf of sensor graph and allows you to query them later.

Current State of Necessary TODOS:
- [ ] Support dumping and restoring state
- [ ] Support config variables for RSL behavior
    - [ ] fill-stop config
- [ ] Support fill-stop mode
- [X] Support direct interaction with the rsl via rpcs
- [ ] Support final RPCs
    - [ ] rsl_highest_id
    - [ ] rsl_dump_stream_seek
"""

import threading
from builtins import range
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.reports import IOTileReading
from iotile.sg import SensorLog, DataStream, DataStreamSelector
from iotile.sg.exceptions import StorageFullError, StreamEmptyError, UnresolvedIdentifierError
from ...constants import rpcs, pack_error, Error, ControllerSubsystem, SensorLogError


class SensorLogSubsystem(object):
    """Container for raw sensor log state."""

    def __init__(self, model):
        self.storage = SensorLog(model=model)
        self.dump_walker = None
        self.next_id = 1
        self.mutex = threading.Lock()

    def clear(self):
        """Clear all data from the RSL."""

        with self.mutex:
            self.storage.clear()

    def clear_to_reset(self, _config_vars):
        """Clear all volatile information across a reset."""

        with self.mutex:
            self.storage.destroy_all_walkers()
            self.dump_walker = None

    def count(self):
        """Count many many readings are persistently stored.

        Returns:
            (int, int): The number of readings in storage and output areas.
        """

        with self.mutex:
            return self.storage.count()

    def allocate_id(self):
        """Get the next unique ID.

        Returns:
            int: A unique reading ID.
        """

        with self.mutex:
            next_id = self.next_id
            self.next_id += 1

        return next_id

    def push(self, stream_id, timestamp, value, reading_id=None):
        """Push a value to a stream.

        Args:
            stream_id (int): The stream we want to push to.
            timestamp (int): The raw timestamp of the value we want to
                store.
            value (int): The 32-bit integer value we want to push.
            reading_id (int): Optional reading ID to force, otherwise
                an ID will be assigned automatically if needed.
        Returns:
            int: Packed 32-bit error code.
        """

        stream = DataStream.FromEncoded(stream_id)
        if stream.buffered and reading_id is None:
            reading_id = self.allocate_id()

        reading = IOTileReading(stream_id, timestamp, value, reading_id=reading_id)

        try:
            with self.mutex:
                self.storage.push(stream, reading)

            return Error.NO_ERROR
        except StorageFullError:
            return pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.RING_BUFFER_FULL)

    def inspect_virtual(self, stream_id):
        """Inspect the last value written into a virtual stream.

        Args:
            stream_id (int): The virtual stream was want to inspect.

        Returns:
            (int, int): An error code and the stream value.
        """

        stream = DataStream.FromEncoded(stream_id)

        if stream.buffered:
            return [pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.VIRTUAL_STREAM_NOT_FOUND), 0]

        try:
            with self.mutex:
                reading = self.storage.inspect_last(stream, only_allocated=True)
                return [Error.NO_ERROR, reading.value]
        except StreamEmptyError:
            return [Error.NO_ERROR, 0]
        except UnresolvedIdentifierError:
            return [pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.VIRTUAL_STREAM_NOT_FOUND), 0]

    def dump_begin(self, selector_id):
        """Start dumping a stream.

        Args:
            selector_id (int): The buffered stream we want to dump.

        Returns:
            (int, int, int): Error code, second error code, number of available readings
        """

        with self.mutex:
            if self.dump_walker is not None:
                self.storage.destroy_walker(self.dump_walker)

            selector = DataStreamSelector.FromEncoded(selector_id)
            self.dump_walker = self.storage.create_walker(selector, skip_all=False)

        return Error.NO_ERROR, Error.NO_ERROR, self.dump_walker.count()

    def dump_next(self):
        """Dump the next reading from the stream.

        Returns:
            IOTileReading: The next reading or None if there isn't one
        """

        try:
            with self.mutex:
                return self.dump_walker.pop()
        except StreamEmptyError:
            return None


class RawSensorLogMixin(object):
    """Reference controller subsystem for the raw sensor log.

    This class must be used as a mixin with a ReferenceController base class.

    Args:
        model (DeviceModel): The device model to use to calculate
            constraints and other operating parameters.
    """


    def __init__(self, model):
        self.sensor_log = SensorLogSubsystem(model)
        self._post_config_subsystems.append(self.sensor_log)

    @tile_rpc(*rpcs.RSL_PUSH_READING)
    def rsl_push_reading(self, value, stream_id):
        """Push a reading to the RSL directly."""

        #FIXME: Fix this with timestamp from clock manager task
        err = self.sensor_log.push(stream_id, 0, value)
        return [err]

    @tile_rpc(*rpcs.RSL_PUSH_MANY_READINGS)
    def rsl_push_many_readings(self, value, count, stream_id):
        """Push many copies of a reading to the RSL."""

        #FIXME: Fix this with timestamp from clock manager task

        for i in range(1, count+1):
            err = self.sensor_log.push(stream_id, 0, value)
            if err != Error.NO_ERROR:
                return [err, i]

        return [Error.NO_ERROR, count]

    @tile_rpc(*rpcs.RSL_COUNT_READINGS)
    def rsl_count_readings(self):
        """Count how many readings are stored in the RSL."""

        storage, output = self.sensor_log.count()
        return [Error.NO_ERROR, storage, output]

    @tile_rpc(*rpcs.RSL_CLEAR_READINGS)
    def rsl_clear_readings(self):
        """Clear all data from the RSL."""

        self.sensor_log.clear()
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.RSL_INSPECT_VIRTUAL_STREAM)
    def rsl_inspect_virtual_stream(self, stream_id):
        """Inspect the last value in a virtual stream."""

        return self.sensor_log.inspect_virtual(stream_id)

    @tile_rpc(*rpcs.RSL_DUMP_STREAM_BEGIN)
    def rsl_dump_stream_begin(self, stream_id):
        """Begin dumping the contents of a stream."""

        err, err2, count = self.sensor_log.dump_begin(stream_id)

        #FIXME: Fix this with the uptime of the clock manager task
        return [err, err2, count, 0]

    @tile_rpc(*rpcs.RSL_DUMP_STREAM_NEXT)
    def rsl_dump_stream_next(self, output_format):
        """Dump the next reading from the output stream."""

        timestamp = 0
        stream_id = 0
        value = 0
        reading_id = 0
        error = Error.NO_ERROR

        reading = self.sensor_log.dump_next()
        if reading is not None:
            timestamp = reading.raw_time
            stream_id = reading.stream
            value = reading.value
            reading_id = reading.reading_id
        else:
            error = pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.NO_MORE_READINGS)

        if output_format == 0:
            raise ValueError("Old output format for dump_stream not yet supported")
        elif output_format != 1:
            raise ValueError("Output format other than 1 not yet supported")

        return [error, timestamp, value, reading_id, stream_id, 0]
