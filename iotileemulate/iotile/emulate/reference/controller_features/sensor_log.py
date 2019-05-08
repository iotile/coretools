"""Mixin for the raw sensor log.

The raw sensor log is the subsystem that stores sensor readings
on behalf of sensor graph and allows you to query them later.

The main purpose of this subsystem is to serve as a persistent
data store.  Since it allocates `StreamWalker` objects that
are used by the SensorGraph and Streaming subsystems, it needs
to have a very clear dump()/restore() process to ensure that
those subsystems properly get their stream walkers restored
to the correct state.
"""

import struct
import logging
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.reports import IOTileReading
from iotile.sg import SensorLog, DataStream, DataStreamSelector
from iotile.sg.engine import InMemoryStorageEngine
from iotile.sg.exceptions import StorageFullError, StreamEmptyError, UnresolvedIdentifierError
from ...constants import rpcs, pack_error, Error, ControllerSubsystem, SensorLogError, streams
from .controller_system import ControllerSubsystemBase

class SensorLogSubsystem(ControllerSubsystemBase):
    """Container for raw sensor log state."""

    def __init__(self, emulator, model):
        super(SensorLogSubsystem, self).__init__(emulator)

        self.engine = InMemoryStorageEngine(model=model)
        self.storage = SensorLog(self.engine, model=model, id_assigner=lambda x, y: self.allocate_id())
        self.dump_walker = None
        self.next_id = 1
        self._logger = logging.getLogger(__name__)

    def dump(self):
        """Serialize the state of this subsystem into a dict.

        Returns:
            dict: The serialized state
        """

        walker = self.dump_walker
        if walker is not None:
            walker = walker.dump()

        state = {
            'storage': self.storage.dump(),
            'dump_walker': walker,
            'next_id': self.next_id
        }

        return state

    def prepare_for_restore(self):
        """Prepare the SensorLog subsystem for a restore.

        This must be called at the start of the restore to clear all of the
        stream walkers in the SensorLog storage engine, which are then added
        back by the SensorGraph and Streaming subsystems and then restored
        to their previous positions when restore() is called on this subsystem.
        """

        self.storage.destroy_all_walkers()

    def restore(self, state):
        """Restore the state of this subsystem from a prior call to dump().

        Calling restore must be properly sequenced with calls to other
        subsystems that include stream walkers so that their walkers are
        properly restored.

        Args:
            state (dict): The results of a prior call to dump().
        """

        self.storage.restore(state.get('storage'))

        dump_walker = state.get('dump_walker')
        if dump_walker is not None:
            dump_walker = self.storage.restore_walker(dump_walker)

        self.dump_walker = dump_walker
        self.next_id = state.get('next_id', 1)

    def clear(self, timestamp):
        """Clear all data from the RSL.

        This pushes a single reading once we clear everything so that
        we keep track of the highest ID that we have allocated to date.

        This needs the current timestamp to be able to properly timestamp
        the cleared storage reading that it pushes.

        Args:
            timestamp (int): The current timestamp to store with the
                reading.
        """

        self.storage.clear()

        self.push(streams.DATA_CLEARED, timestamp, 1)

    def clear_to_reset(self, config_vars):
        """Clear all volatile information across a reset."""

        self._logger.info("Config vars in sensor log reset: %s", config_vars)
        super(SensorLogSubsystem, self).clear_to_reset(config_vars)

        self.storage.destroy_all_walkers()
        self.dump_walker = None

        if config_vars.get('storage_fillstop', False):
            self._logger.debug("Marking storage log fill/stop")
            self.storage.set_rollover('storage', False)

        if config_vars.get('streaming_fillstop', False):
            self._logger.debug("Marking streaming log fill/stop")
            self.storage.set_rollover('streaming', False)

    def count(self):
        """Count many many readings are persistently stored.

        Returns:
            (int, int): The number of readings in storage and output areas.
        """

        return self.storage.count()

    def allocate_id(self):
        """Get the next unique ID.

        Returns:
            int: A unique reading ID.
        """

        next_id = self.next_id
        self.next_id += 1

        return next_id

    def push(self, stream_id, timestamp, value):
        """Push a value to a stream.

        Args:
            stream_id (int): The stream we want to push to.
            timestamp (int): The raw timestamp of the value we want to
                store.
            value (int): The 32-bit integer value we want to push.
        Returns:
            int: Packed 32-bit error code.
        """

        stream = DataStream.FromEncoded(stream_id)
        reading = IOTileReading(stream_id, timestamp, value)

        try:
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

        if self.dump_walker is not None:
            self.storage.destroy_walker(self.dump_walker)

        selector = DataStreamSelector.FromEncoded(selector_id)
        self.dump_walker = self.storage.create_walker(selector, skip_all=False)

        return Error.NO_ERROR, Error.NO_ERROR, self.dump_walker.count()

    def dump_seek(self, reading_id):
        """Seek the dump streamer to a given ID.

        Returns:
            (int, int, int): Two error codes and the count of remaining readings.

            The first error code covers the seeking process.
            The second error code covers the stream counting process (cannot fail)
            The third item in the tuple is the number of readings left in the stream.
        """

        if self.dump_walker is None:
            return (pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.STREAM_WALKER_NOT_INITIALIZED),
                    Error.NO_ERROR, 0)

        try:
            exact = self.dump_walker.seek(reading_id, target='id')
        except UnresolvedIdentifierError:
            return (pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.NO_MORE_READINGS),
                    Error.NO_ERROR, 0)

        error = Error.NO_ERROR
        if not exact:
            error = pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.ID_FOUND_FOR_ANOTHER_STREAM)

        return (error, Error.NO_ERROR, self.dump_walker.count())

    def dump_next(self):
        """Dump the next reading from the stream.

        Returns:
            IOTileReading: The next reading or None if there isn't one
        """

        if self.dump_walker is None:
            return pack_error(ControllerSubsystem.SENSOR_LOG, SensorLogError.STREAM_WALKER_NOT_INITIALIZED)

        try:
            return self.dump_walker.pop()
        except StreamEmptyError:
            return None

    def highest_stored_id(self):
        """Scan through the stored readings and report the highest stored id.

        Returns:
            int: The highest stored id.
        """

        shared = [0]
        def _keep_max(_i, reading):
            if reading.reading_id > shared[0]:
                shared[0] = reading.reading_id

        self.engine.scan_storage('storage', _keep_max)
        self.engine.scan_storage('streaming', _keep_max)

        return shared[0]


class RawSensorLogMixin(object):
    """Reference controller subsystem for the raw sensor log.

    This class must be used as a mixin with a ReferenceController base class.

    Args:
        model (DeviceModel): The device model to use to calculate
            constraints and other operating parameters.
    """


    def __init__(self, emulator, model):
        self.sensor_log = SensorLogSubsystem(emulator, model)
        self._post_config_subsystems.append(self.sensor_log)

        # Declare all of our config variables
        self.declare_config_variable('storage_fillstop', 0x2004, 'uint8_t', default=False, convert='bool')
        self.declare_config_variable('streaming_fillstop', 0x2005, 'uint8_t', default=False, convert='bool')


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

        #FIXME: Fix this with timestamp from clock manager task
        self.sensor_log.clear(0)
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

    @tile_rpc(*rpcs.RSL_DUMP_STREAM_SEEK)
    def rsl_dump_stream_seek(self, reading_id):
        """Seek a specific reading by ID."""

        return self.sensor_log.dump_seek(reading_id)

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
            return [struct.pack("<LLL", error, timestamp, value)]
        elif output_format != 1:
            raise ValueError("Output format other than 1 not yet supported")

        return [struct.pack("<LLLLH2x", error, timestamp, value, reading_id, stream_id)]

    @tile_rpc(*rpcs.RSL_HIGHEST_READING_ID)
    def rsl_get_highest_saved_id(self):
        """Get the highest saved reading id."""

        highest_id = self.sensor_log.highest_stored_id()
        return [Error.NO_ERROR, highest_id]
