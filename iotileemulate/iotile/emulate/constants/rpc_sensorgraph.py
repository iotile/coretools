r"""RPCs implemented by the SensorGraph subsystem on an IOTile controller.

The SensorGraph subsystem is designed to allow you to embed a small set
automatic actions that should be run whenever events happen inside the device.
Sensorgraph is structured as a dependency tree where actions are linked by
named FIFOs that route data from inputs -> processing functions -> output
sinks.

The sensor-graph language and implementation were designed to facilitate
static analysis of maximum resource needs as well as runtime properties like
power consumption.

The sensor-graph subsystem interacts with the sensor-log and stream-manager
subsystems in the following way:

sensor-graph has rules that respond to events on a device and generate data
in named FIFOs called streams.  All of the actual data storage and stream
management on behalf of sensor-graph is handled by the sensor-log subsystem.

The streaming subsystem listens on configured streams to see if it should
package them up and send them to an external user in the form of a `report`.

So the interaction diagram looks like:


    sensor-graph       <------XXXX------>   stream-manager
                       no direct contact

    generates data in streams               sole purpose in life is to
    according to configured rules           build reports from streams

                    \\                  //
      producer       \\                //   consumer only
      and consumer    \\              //    (generates no readings!)
                          sensor-log

                          stores all streams and lets you
                          inspect their contents using
                          stream walkers that automatically
                          get updated when new data is available.

The actual work of simulating the functionality of the embedded sensor-graph
engine is performed by the iotile-sensorgraph package that makes it available
in a variety of contexts including a direct command line simulator named
iotile-sgrun as well as an optimizing compiler.
"""

from iotile.core.hw.virtual import RPCDeclaration


SG_COUNT_NODES = RPCDeclaration(0x2002, "", "L")
"""Count the number of nodes currently in the sensor graph.

This RPC just returns the number of nodes currently added
to the sensor graph.  It can be called at any time and
cannot fail.

Returns:
  - uint32_t: The number of nodes currently present.
"""

SG_ADD_NODE = RPCDeclaration(0x2003, "20s", "L")
"""Add a node to the current sensor graph.

This RPC is designed to be called repeatedly to build up a sensor graph. You
call it with a complicated binary descriptor object that describes the node
you want to build and the sensor-graph engine adds that node to its internal
graph structure.  There are a number of potential error codes that can be
returned if there is an inssue with your node descriptor.

This is a synchronous RPC, so when it returns the node has already been added
to the graph and it is ready for usage.

It is safe to call this RPC at any point, even when the sensor-graph engine
is enabled.

You can see the structure of a node descriptor and convert it to/from a nice
human-readable string using routines from `iotile.sg.node_descriptor`:

  - parse_binary_node_descriptor()
  - create_binary_descriptor()

Args:
  - char[20]: A complex serialized binary node descriptor.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - INVALID_NODE_STREAM: You cannot create a node with an output stream of
    type 'input'. 'input' streams are global sensor-graph inputs so they
    cannot be generated as the result of node.  They are created using the
    SG_GRAPH_INPUT RPC.
  - NO_NODE_SPACE_AVAILABLE: You have run out of space for new graph nodes.
  - NO_AVAILABLE_OUTPUTS: Each node has a preallocated array linking it to any
    possible output nodes that should be triggered it produces a new reading.
    If you have a node that fans out too quickly, you may get this error.  It
    can be fixed by inserting another node to buffer the output.
"""

SG_GRAPH_INPUT = RPCDeclaration(0x2004, "LH", "L")
"""Present a new input to the sensor graph.

This is the only method you can call to trigger the sensor-graph engine to
process a new reading.  While you can directly push readings to the underly
rsl streams using RSL_PUSH, that method is not guaranteed to fire relevant
sensor-graph rules and must be used with extreme caution when there is a
loaded sensor-graph.

You specify the stream that you want to push to, which should be an input
class stream and the value that you want to push.  It will automatically be
timestamped with the current utc time or up-time of the controller.

**This is an asynchronous RPC.**

Unlike most sensor-graph related RPCs, this RPC will return immediately after
queueing the input and not wait until it is fully processed.  This behavior is
critical since the processing of the input may require calling an RPC because
it triggered a node that has a `call_rpc` processing function.  If we were
waiting synchronously for processing to be finished this would deadlock since
the RPC bus would be blocked so the `call_rpc` function would hang and we
would wait forever.

Args:
  - uint32_t: The reading value that you wish to present to the sensor-graph
    engine.  If no nodes are configured to listen to this input, it will be
    ignored silently.
  - uint16_t: The stream id of the **input stream** that you want to push.
    This must be an **input** stream.

Returns:
  - uint32_t: An error code.  There are currently no errors possible.
"""


SG_SET_ONLINE = RPCDeclaration(0x2005, "H", "L")
"""Pause or resume the sensor-graph engine.

If you call SG_SET_ONLINE with a false value, it will pause the processing
or all future inputs until you call SG_SET_ONLINE with a true value.

Pausing means that any call to SG_GRAPH_INPUT will be dropped.  All other
functionality still works the same whether the graph is paused or resumed.

It is always safe to gratuitously call this RPC with the same state.  This is
good because there is no way to determine whether the sensor-graph is
currently paused or resumed.

Args:
  - uint16_t: A true value to enable the sensor-graph and a false value to disable it.

Returns:
  - uint32_t: An error code.  Currently, there are no possible errors that could be
    returned.
"""

SG_ADD_STREAMER = RPCDeclaration(0x2007, "V", "L")
"""Add a streamer to the sensor-graph.

A streamer is a resource inside the sensor-graph subsystem that packages up
readings in one or more streams (that you select with a selector programmed as
part of the streamer resource).  Whenever given conditions are met, the
streamer will package up all of its readings into a report that it sends out
of the device using the device's streaming interface.

You specify how the streamer should be configured by using a binary streamer
descriptor similar to how you specify a node using a node descriptor structure.

You can see the descriptor structure and utility functions in the module:
iotile.sg.streamer

The streamers are added sequentially every time you call SG_ADD_STREAMER so
the first time you call this RPC, the streamer will get index 0, the next
call will be index 1, etc.

Args:
  - char[14]: A binary streamer descriptor.  The final byte is padding though
    so you can pass either 13 or 14 bytes of data.

Returns:
  - uint32_t: an error code.

Possible Errors:
  - NO_MORE_STREAMER_RESOURCES: There are no more available streamer
    resources.
"""

#FIXME: Move streamer info structure to iotile.sg
SG_QUERY_STREAMER = RPCDeclaration(0x200a, "H", "V")
"""Query the current status of a streamer resource by its index.

This method can be called at any time to inspect the current status of a
streamer. You can learn things like when the last time it was triggered was,
what error code was returned the last time it was triggered and whether it is
currently in the process of creating and/or streaming a report.

Polling this RPC is the correct way to determine what a streamer is doing.

Args:
  - uint16_t: The index of the streamer that you wish to query.

Returns (option 1):
  - char[20]: A binary streamer status structure.

Returns (option 2):
  - uint32_t: An error code in case the index is invalid.

Possible Errors:
  - STREAMER_NOT_ALLOCATED: If the index corresponds to a streamer that has
    not been allocated.
"""

SG_RESET_GRAPH = RPCDeclaration(0x200d, "", "L")
"""Clear the current sensor-graph in ram and also any persisted graph.

This function completely clears any stored sensor-graph nodes or streamers. It
does not impact any data stored in the raw sensor log.

There is no way to clear just the persisted sensor-graph or the one in ram
without also clearing the persisted one.

This function will also clear the persistent storagea of any received streamer
acknowledgement values.  See SG_SEEK_STREAMER for a discussion of what these
values are used for.

Returns:
  - uint32_t: An error code.  No errors are currently possible.
"""

SG_PERSIST_GRAPH = RPCDeclaration(0x200e, "", "L")
"""Save the sensor-graph currently in memory to persistent storage.

The normal way you build up a sensor-graph is by repeatedly calling
SG_ADD_NODE and SG_ADD_STREAMER until you have the desired graph
structure in memory.

Then you call SG_PERSIST_GRAPH to save that to persistent storage. Once you
call SG_PERSIST_GRAPH, the sensor-graph will automatically be loaded and start
running every time the device resets so this is also the way you "launch" the
device onto its autonomous mission.

This is a synchronous RPC, so it does not return until the graph is completely
persisted.

Returns:
  - uint32_t: An error code.  No errors are currently possible.
"""

SG_SEEK_STREAMER = RPCDeclaration(0x200f, "HHL", "L")
"""Inform the given streamer about what readings have been successfully received.

Streamer resources are designed to act like reliable TCP streams that never
throw away data until it is positively acknowledged as received by the remote
party.  Since the streaming interface is unidirectional, there needs to be a
way for that remote party to inform the sensor-graph subsystem that it has
received all readings up to sequence number X.

That is the purpose of this seek streamer RPC.  It lets a remote party
gratuitious inform the IOTile device what the highest reading_id is has
received from each streamer.  This is used to advance an internal pointer in
each streamer resource to not send any of that data again.

Since these acknowledgement values may be received via intermediaries that may
have out of date information, by default the acknowledgement value can only
ever increase (which should be the case in reality).  This makes it safe for
everyone to just gratuitously send their highest acknowledgement value
whenever they get a chance and the IOTile device will ignore old values.

If you need to roll a streamer back to fix an error where you acknowledged a
reading but then later lost it, you can set the force parameter in this RPC to
true and it will accept whatever acknowledgement value you set, even if it is
lower than what it currently has stored.

The behavior of this RPC when an incorrect acknowledgement value is given
can be counterintuitive so it's important to understand what will happend when
each of the following error codes are returned:

  - STREAMER_NOT_ALLOCATED: No change
  - OLD_ACKNOWLEDGE_UPDATE: No change
  - ID_FOUND_FOR_ANOTHER_STREAM: This is a protocol error, so the streamer attempts
    to get back in sync with the remote party by pointing itself at the oldest
    selected reading.
  - NO_MORE_READINGS: The streamer will skip all readings and point at the end
    of the storage area.

This specific behavior is not to considered stable, documented behavior since
it is undesireable in many cases.  A future variant of the iotile controller
may change how streamers react to protocol errors.

Args:
  - uint16_t: The index of the streamer you want to acknowledge.
  - uint16_t: true to force a rollback, false to ignroe the acknowledgement if
    it would roll this streamer backward in time.
  - uint32_t: The highest reading_id that the RPC caller is claiming to have
    received.  The streamer will no longer send readings in reports that have
    reading ids <= this value.

Returns:
  - uint32_t: an error code.

Possible Errors:
  - STREAMER_NOT_ALLOCATED: If the index corresponds to a streamer that has
    not been allocated.
  - OLD_ACKNOWLEDGE_UPDATE: The acknowledgement value is smaller than what is
    currently stored for this streamer and force was false.  If you need to
    roll the streamer back you need to pass the force parameter as true.
  - ID_FOUND_FOR_ANOTHER_STREAM: The reading_id passed corresponds to a reading
    that was never selected by this streamer so it cannot have been received.
  - NO_MORE_READINGS: The reading_id passed is greater than all reading ids
    stored in this iotile device to it cannot possibly have actually have
    been received.
"""

SG_TRIGGER_STREAMER = RPCDeclaration(0x2010, "H", "L")
"""Manually trigger a stream to attempt to create/stream a report immediately.

This function can be used to test out a streamer or as part of an action
programmed into your sensor-graph script to control when the device attempts
to send data remotely.

Just because you call this function on a valid streamer does not mean it will
necessarily generate a report.  It also needs to have unacknowledged data that
needs to be streamed.  You can inspect the return value of this RPC to see
whether a report was indeed queued for streaming.

Args:
  - uint16_t: The index of the streamer that you want to trigger.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - STREAMER_NOT_ALLOCATED: If the index corresponds to a streamer that has
    not been allocated.
  - STREAM_ALREADY_IN_PROGRESS: The streamer is currently creating a report
    so you cannot trigger it again until it finishes and returns to the
    idle state.
  - STREAMER_HAS_NO_NEW_DATA: The streamer does not have any unacknowledged
    readings to send so the report would be empty.  No report is generated
    in this case.
  - INVALID_STREAM_DESTINATION: The configured tile that this streamer is
    supposed to send its report to does not exist.  This is usually a fatal
    configuration error telling you that your streamer is misconfigured.
"""

SG_INSPECT_GRAPH_NODE = RPCDeclaration(0x2016, "H", "20s")
"""Get the binary node descriptor from a node by its index.

This allows you to verify the action of the SG_ADD_NODE RPC by inspecting the
last node added to the sensor-graph.  The binary descriptor returned should
be identical to what you used to create it.

This RPC is also useful for inspecting what sensor-graph is programmed into a
given device by iterating over all nodes and returning their node descriptors.

**If the given index is not in use, this RPC will not complete normally but
instead fail with an UNKNOWN_ERROR error status.**

These kinds of error statuses are normally translated into HardwareError
exceptions by CoreTools.

Args:
  - uint16_t: The index of the node that you wish to inspect.

Returns:
  - char[20]: A binary node descriptor for the node in question.
"""

SG_INSPECT_STREAMER = RPCDeclaration(0x2017, "H", "L14s2x")
"""Get a binary streamer descriptor describing a streamer by its index.

This allows you to verify the action of the SG_ADD_STREAMER RPC by inspecting
the last streamer added to the sensor-graph.  The binary descriptor returned should
be identical to what you used to create it.

This RPC is also useful for inspecting what sensor-graph is programmed into a
given device by iterating over all streamers and returning their streamer descriptors.

Calling this RPC repeatedly along with SG_INSPECT_GRAPH_NODE will let you dump
a sensor-graph out of an IOTile device.

Args:
  - uint16_t: The index of the streamer that you wish to dump.

Returns:
  - uint32_t: An error code.
  - char[14]: A binary streamer descriptor suitable for passing to SG_ADD_STREAMER.

Possible Errors:
  - STREAMER_NOT_ALLOCATED: If the index corresponds to a streamer that has
    not been allocated.
"""
