"""RPCs implemented by the RawSensorLog (RSL) subsystem on an IOTile controller.

The raw sensor log, abbreviated RSL, is the persistent storage subsystem
inside of an IOTile controller.  It's job is to provide a series of named
FIFOs that can be used as multi-producer, multi-consumer queues.  Each queue
is assigned a name and any consumer that attaches to it can poll for any new
data since the last time they checked.

Each queue is assigned a storage class which specifies whether the data in the
queue is persistent, so it will survice a device reset or volatile, so it will
not.  Volatile queues are also called "virtual" queues inside the RSL, since
they do not need to actually allocate a persistent FIFO data structure while
still giving the appearance that one exists.

The major subsystems that interact with the RSL are SensorGraph and
StreamManager.

  - SensorGraph uses a series of rules to produce data and assigns each data a
    "stream" name.  These streams map 1-1 onto the RSL queues, so there is a
    single RSL queue for every SensorGraph stream.  The terms queue, FIFO and
    stream in this context are 100% synonomous.

    Internally Sensorgraph also uses streams to cache data that will be
    consumed by later rules.

  - StreamManager consumes streams/queues from the RSL and when given
    conditions are met, it packages up all or a subset of the readings in a
    given set of queues into a report, which is a a signed list of readings
    that can be sent out of the IOTile device through its Streaming Interface.

In most subsequent documentation, the word **stream** will be used to refer to
uniformly to both virtual and persistent queues allocated in the RSL
subsystem.

ALl errors returned by an RPC declared below will have the subsystem set to
SENSOR_LOG_SUBSYSTEM and the error code set to something in Error or
SensorLogError.

The RPCs below allow for direct inspection and interaction with the RSL. In
particular, they can be used for:

  - pushing readings directly to the RSL subsystem
  - querying status on memory usage
  - dumping all readings by stream name
  - clearing all data from the RSL
"""

from iotile.core.hw.virtual import RPCDeclaration


RSL_PUSH_READING = RPCDeclaration(0x2000, "LH", "L")
"""Push a single reading into a stream.

You call this RPC with the 32-bit value you want to push and the 16-bit stream
name and this RPC synchronously pushes the value to the stream.  This is a
direct push to the RSL that the does not go through the SensorGraph subsystem
at all so it is not guaranteed to immediately trigger any sensor graph rules
that may apply to that stream unless the stream is of class input.

Args:
  - uint32_t: The new value that we want to push.  This can be anything that
    fits in 32-bits.
  - uin16_t: An encoded StreamID that specifies the stream that we wish to
    push to.

Returns:
  - uint32_t: An error Code.

Possible Errors:
  - RING_BUFFER_FULL: The persistent RSL queue that would store this reading
    is in fill-stop mode and it is currently full.
  - VIRTUAL_STREAM_NOT_FOUND: The stream name passed specifies a virtual
    stream and there are no stream walkers configured that listen to that stream.
    Virtual streams directly store their readings in the walkers of all of their
    consumers so there is no place for this reading to go.
"""

RSL_PUSH_MANY_READINGS = RPCDeclaration(0x2013, "LLH", "LL")
"""Push multiple copies of the same value to a given stream.

This RPC is primarily useful for testing purposes.  It can quickly fill the
RSL with data.  Conceptually this is equivalent to N calls to RSL_PUSH_READING
with the same value and stream id but since it happens inside a single RPC, it
is signficantly faster (no RPC overhead per reading).

In practice this RPC be 100-1000 times faster when you need to push a lot of
data and don't need the values to be different.

This RPC stops as soon as the first error is returned from pushing a reading.
You can learn how many readings were actually pushed by inspecting the return
value.

Args:
  - uint32_t: The value to push N copies of
  - uint32_t: The number of copies to push.
  - uint16_t: The stream to push the readings to.

Returns:
  - uint32_t: An error code.
  - uint32_t: The number of readings that were successfully pushed.

Possible Errors:
  - RING_BUFFER_FULL: The persistent RSL queue that would store this reading
    is in fill-stop mode and it is currently full.
  - VIRTUAL_STREAM_NOT_FOUND: The stream name passed specifies a virtual
    stream and there are no stream walkers configured that listen to that stream.
    Virtual streams directly store their readings in the walkers of all of their
    consumers so there is no place for this reading to go.
"""

RSL_COUNT_READINGS = RPCDeclaration(0x2001, "", "3L")
"""Count how many persistent readings are stored in the RSL.

The RSL maintains two persistent storage areas: one for output class streams
and one for storage (also called buffered) class streams.  This RPC just
returns the count of readings stored in each of those two persistent storage
areas.

Returns:
  - uint32_t: An error code.  No error codes are currently possible.
  - uint32_t: The number of readings currently stored in the storage area of the
    RSL.
  - uint32_t: The number of readings currently stored in the output area of the
    RSL.
"""

RSL_HIGHEST_READING_ID = RPCDeclaration(0x2011, "", "LL")
"""Return the highest reading ID current in the RSL.

All readings in the RSL that are stored persistently are assigned a
monotonically increasing sequence number called their reading id.

This RPC returns the highest ID that is currently stored in the RSL. These
unique IDs are also assigned to non-reading objects like streamer reports so
the return value of this RPC is not guaranteed to be the highest ID ever
allocated but it is guaranteed to be the highest ID ever allocated to a
reading.

Returns:
  - uint32_t: An error code.  No errors are currently possible.
  - uint32_t: The highest reading ID currently assigned to a reading in the
    RSL.
"""

RSL_CLEAR_READINGS = RPCDeclaration(0x0200c, "", "L")
"""Clear all of the readings inside the RSL.

This will clear both persistently stored readings as well as all virtual
readings except for constant class streams.  This method pushes a single
system output reading to indicate that the RSL has been cleared so the result
of this RPC will be:
  - all virtual streams cleared except constant streams
  - all current storage and output streams cleared
  - a single output reading pushed

Returns:
  - uint32_t: An error code.  There are currently no possible errors.
"""

RSL_INSPECT_VIRTUAL_STREAM = RPCDeclaration(0x200b, "H", "LL")
"""Inspect the value current stored in a virtual stream.

This RPC will show the value inside of a virtual stream.  Since virtual
streams do not have any persistent storage backing, they only have room
for a single value, which this RPC returns.

Also, since virtual streams store their values directly in the stream
walkers that are consuming their data, if there are no stream walkers
allocated for a given virtual stream, this RPC will return an error
since there is no data location to inspect.

Args:
  - uint16_t: The stream ID that we wish to inspect.  This should be
    a virtual class stream.

Returns:
  - uint32_t: An error code.
  - uint32_t: The value currently stored in the named stream.  This is
    only valid if NO_ERROR is returned.

Possible Errors:
  - VIRTUAL_STREAM_NOT_FOUND: There is no allocated stream walker that
    listens on the given virtual stream.
"""

RSL_DUMP_STREAM_BEGIN = RPCDeclaration(0x2008, "H", "LLLL")
"""Start dumping all data in a given persistent stream.

Unlike most RPCs, this RPC is not atomic and must be called in a proper
sequence for correct results.  The purpose of the sequence of RPCs is to
download all of the readings stored in a given stream in the RSL.  Since
there is a variable amount of data in the stream, the sequence of RPCs
needed to download it are:

  - RSL_DUMP_STREAM_BEGIN: Start the dump process and allocate an internal
    controller structure to track where we are in the stream.
  - RSL_DUMP_STREAM_SEEK (Optional): Optionally seek to a specific point in
    the stream by reading id.  If this RPC is not sent, the dump always starts
    at the beginning of the stream.
  - RSL_DUMP_STREAM_NEXT: Return the next reading in the stream and an error
    if we are at the end of the stream.

It is always safe to call RSL_DUMP_STREAM_BEGIN but this will clear out the
state from any previous dumping process so the client must ensure that only a
single dump happens at a time.

Args:
  - uint16_t: The encoded stream id of the stream that we wish to dump.  This
    must be a storage or output class stream.  If you are trying to inspect a
    virtual stream, use RSL_INSPECT_VIRTUAL_STREAM instead.

Returns:
  - uint32_t: An error code covering the allocation of the internal walker
    resource. No current error codes are possible.
  - uint32_t: A second error code covering the counting of available readings
    in the stream.  No current error codes are possible.
  - uint32_t: The number of available readings.  You should be able to call
    RSL_DUMP_STREAM_NEXT exactly this many times without error.  However, keep
    in mind that readings may be added or overwritten as you iterate so you
    should inspect the actual return value of RSL_DUMP_STREAM_NEXT to know
    when you are finished.
  - uint32_t: The current uptime of the controller.  This is necessary for
    proper conversion of readings stamped with controller uptime into actual
    UTC time.
"""

RSL_DUMP_STREAM_SEEK = RPCDeclaration(0x2012, "L", "3L")
"""Seek to a specific reading id inside the stream we are currently dumping.

See RSL_DUMP_STREAM_BEGIN for more details on the stream dumping process.
This method is optional and will move the read pointer so that it points to
the reading with the given reading ID.

Make sure you understand the behavior of what happens when you seek to a
stream id that either does not exist or is not part of the stream in question.

There are 3 possible cases that can happen when seeking a stream by reading_id:

  - The reading ID could not exist.  In this case the current location of the
    stream is unchanged and an error is returned.
  - The reading ID could be found but correspond with a reading not in this
    stream. In this case the stream location is set to the first reading with
    id after the desired seek_id.  An error code is returned but the stream
    location is changed.
  - The reading ID is found within the given stream.  In this case the stream
    location is updated to point at the specific reading id and NO_ERROR is
    returned.

Args:
  - uint32_t: The reading ID to seek.

Returns:
  - uint32_t: An error code covering the seek process.
  - uint32_t: An error code covering the counting of available readings.
  - uint32_t: The number of available readings after the seek.

Possible Errors:
  - STREAM_WALKER_NOT_INITIALIZED: If this RPC was not called after first
    calling RSL_DUMP_STREAM_BEGIN to set the desired stream id and allocate
    internal resources.
  - CANNOT_USE_UNBUFFERED_STREAM: If the stream id passed to
    RSL_DUMP_STREAM_BEGIN points to a virtual stream.  Virtual streams do not
    have reading ids and cannot be seeked.
  - ID_FOUND_FOR_ANOTHER_STREAM: If the reading id passed was found but
    did not correspond to a reading inside the desired stream.
  - NO_MORE_READINGS: If the reading id was not found at all in the RSL.
"""

RSL_DUMP_STREAM_NEXT = RPCDeclaration(0x2009, "B", "V")
"""Dump the next reading in the previously selected stream.

See RSL_DUMP_STREAM_BEGIN for more details on the stream dumping process.

This RPC will dump a single reading from the currenly selected stream that was
passed to the last call to RSL_DUMP_STREAM_BEGIN.  It's signature has changed
so it takes a single byte argument value that indicates whether the caller
would prefer the new or old return format.  The new return format contains
more information and should always be chosen.  If this flag is omitted or
passed with the value of 0, the old return format will be used.

For the historical record, the old return format, that is no longer used is:
  - uint32_t: An error code.
  - uint32_t: The reading timestamp
  - uint32_t: The reading value

In the v0 return format, there was no way to know the actual stream id of the
reading or its unique reading id.

Args:
  - uint8_t: The desired return format.  If set to 0, an old format will be
    used otherwise, if 1 is passed, the new format will be used.  No value
    other than 0 or 1 should be passed.

Returns (format 0):
  - uint32_t: An error code.
  - uint32_t: The reading timestamp.
  - uint32_t: The reading value.

Returns (format 1):
  - uint32_t: An error code.
  - uint32_t: The reading timestamp.
  - uint32_t: The reading value.
  - uint32_t: The reading's unique reading ID.
  - uint16_t: The reading's stream ID.
  - uint16_t: Reserved, should be ignored.

Possible Errors:
  - NO_MORE_READINGS: If all of the available readings have been exhausted and
    there is no more data.
"""
