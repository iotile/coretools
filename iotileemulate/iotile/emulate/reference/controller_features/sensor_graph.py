r"""The sensorgraph subsystem is an embedded event based scripting engine for IOTile devices.

It is designed to allow you to embed a small set automatic actions that should
be run whenever events happen inside the device.  Sensorgraph is structured as
a dependency tree where actions are linked by named FIFOs that route data from
inputs -> processing functions -> output sinks.

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

This controller subsystem mixin just wraps the underlying sensorgraph
simulator from iotile-sensorgraph and adds the correct RPC based interface to
it to emulate how you interact with sensor-graph in a physical IOTile based
device.

TODO:
  - [ ] Add dump/restore support
  - [ ] Add support for logging information on reset
"""

import logging
import struct
import asyncio
import inspect
from collections import deque
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.exceptions import RPCErrorCode
from iotile.core.hw.reports import IOTileReading
from iotile.sg import DataStream, SensorGraph
from iotile.sg.sim.executor import RPCExecutor
from iotile.sg.node_descriptor import parse_binary_descriptor, create_binary_descriptor
from iotile.sg import streamer_descriptor
from iotile.sg.exceptions import NodeConnectionError, ProcessingFunctionError, ResourceUsageError, UnresolvedIdentifierError, StreamEmptyError
from ...constants import rpcs, pack_error, Error, ControllerSubsystem, SensorGraphError, SensorLogError
from .controller_system import ControllerSubsystemBase

def _pack_sgerror(short_code):
    """Pack a short error code with the sensorgraph subsystem."""

    return pack_error(ControllerSubsystem.SENSOR_GRAPH, short_code)


class StreamerStatus(object):
    """A model representing the state of a streamer resource."""

    def __init__(self):
        self.last_attempt_time = 0
        self.last_success_time = 0
        self.last_error = 0
        self.last_status = 0
        self.attempt_number = 0
        self.comm_status = 0


class EmulatedRPCExecutor(RPCExecutor):
    def __init__(self, device):
        super(EmulatedRPCExecutor, self).__init__()
        self.device = device
        self.logger = logging.getLogger(__name__)

    async def rpc(self, address, rpc_id):
        self.logger.debug("Sending rpc from sensorgraph to %d:%04X", address, rpc_id)

        result, = await self.device.emulator.await_rpc(address, rpc_id, bytes(), resp_format="L")
        return result


class SensorGraphSubsystem(ControllerSubsystemBase):
    """Container for sensor graph state.

    There is a distinction between which sensor-graph is saved into persisted
    storage vs currently loaded and running.  The sensor-graph subsystem runs
    a background task that receives inputs to process and processes them.
    """

    def __init__(self, sensor_log_system, stream_manager, model, emulator, executor=None):
        super(SensorGraphSubsystem, self).__init__(emulator)

        self._logger = logging.getLogger(__name__)

        self._model = model

        self._sensor_log = sensor_log_system.storage
        self._allocate_id = sensor_log_system.allocate_id
        self._inputs = emulator.create_queue(register=True)

        self._stream_manager = stream_manager
        self._rsl = sensor_log_system
        self._executor = executor

        self.graph = SensorGraph(self._sensor_log, model=model, enforce_limits=True)

        self.persisted_exists = False
        self.persisted_nodes = []
        self.persisted_streamers = []
        self.persisted_constants = []

        self.streamer_acks = {}
        self.streamer_status = {}

        self.enabled = False

        # Clock manager linkage
        self.get_timestamp = lambda: 0

    async def _reset_vector(self):
        """Background task to initialize this system in the event loop."""

        self._logger.debug("sensor_graph subsystem task starting")

        # If there is a persistent sgf loaded, send reset information.

        self.initialized.set()

        while True:
            stream, reading = await self._inputs.get()

            try:
                await process_graph_input(self.graph, stream, reading, self._executor)
                self.process_streamers()
            except:  #pylint:disable=bare-except;This is a background task that should not die
                self._logger.exception("Unhandled exception processing sensor_graph input (stream=%s), reading=%s", stream, reading)
            finally:
                self._inputs.task_done()

    def clear_to_reset(self, config_vars):
        """Clear all volatile information across a reset.

        The reset behavior is that:
        - any persisted sensor_graph is loaded
        - if there is a persisted graph found, enabled is set to True
        - if there is a persisted graph found, reset readings are pushed
          into it.
        """

        super(SensorGraphSubsystem, self).clear_to_reset(config_vars)

        self.graph.clear()

        if not self.persisted_exists:
            return

        for node in self.persisted_nodes:
            self.graph.add_node(node)

        for streamer_desc in self.persisted_streamers:
            streamer = streamer_descriptor.parse_string_descriptor(streamer_desc)
            self.graph.add_streamer(streamer)

        # Load in the constants
        for stream, reading in self.persisted_constants:
            self._sensor_log.push(stream, reading)

        self.enabled = True

        # Set up all streamers
        for index, value in self.streamer_acks.items():
            self._seek_streamer(index, value)

        #FIXME: queue sending reset readings

    def process_input(self, encoded_stream, value):
        """Process or drop a graph input.

        This method asynchronously queued an item to be processed by the
        sensorgraph worker task in _reset_vector.  It must be called from
        inside the emulation loop and returns immediately before the input is
        processed.
        """

        if not self.enabled:
            return

        if isinstance(encoded_stream, str):
            stream = DataStream.FromString(encoded_stream)
            encoded_stream = stream.encode()
        elif isinstance(encoded_stream, DataStream):
            stream = encoded_stream
            encoded_stream = stream.encode()
        else:
            stream = DataStream.FromEncoded(encoded_stream)

        reading = IOTileReading(self.get_timestamp(), encoded_stream, value)

        self._inputs.put_nowait((stream, reading))

    def _seek_streamer(self, index, value):
        """Complex logic for actually seeking a streamer to a reading_id.

        This routine hides all of the gnarly logic of the various edge cases.
        In particular, the behavior depends on whether the reading id is found,
        and if it is found, whether it belongs to the indicated streamer or not.

        If not, the behavior depends on whether the sought reading it too high
        or too low.
        """

        highest_id = self._rsl.highest_stored_id()

        streamer = self.graph.streamers[index]
        if not streamer.walker.buffered:
            return _pack_sgerror(SensorLogError.CANNOT_USE_UNBUFFERED_STREAM)

        find_type = None
        try:
            exact = streamer.walker.seek(value, target='id')
            if exact:
                find_type = 'exact'
            else:
                find_type = 'other_stream'

        except UnresolvedIdentifierError:
            if value > highest_id:
                find_type = 'too_high'
            else:
                find_type = 'too_low'

        # If we found an exact match, move one beyond it

        if find_type == 'exact':
            try:
                streamer.walker.pop()
            except StreamEmptyError:
                pass

            error = Error.NO_ERROR
        elif find_type == 'too_high':
            streamer.walker.skip_all()
            error = _pack_sgerror(SensorLogError.NO_MORE_READINGS)
        elif find_type == 'too_low':
            streamer.walker.seek(0, target='offset')
            error = _pack_sgerror(SensorLogError.NO_MORE_READINGS)
        else:
            error = _pack_sgerror(SensorLogError.ID_FOUND_FOR_ANOTHER_STREAM)

        return error

    def acknowledge_streamer(self, index, ack, force):
        """Acknowledge a streamer value as received from the remote side."""

        if index >= len(self.graph.streamers):
            return _pack_sgerror(SensorGraphError.STREAMER_NOT_ALLOCATED)

        old_ack = self.streamer_acks.get(index, 0)

        if ack != 0:
            if ack <= old_ack and not force:
                return _pack_sgerror(SensorGraphError.OLD_ACKNOWLEDGE_UPDATE)

            self.streamer_acks[index] = ack

        current_ack = self.streamer_acks.get(index, 0)
        return self._seek_streamer(index, current_ack)

    def _handle_streamer_finished(self, index, succeeded, highest_ack):
        """Callback when a streamer finishes processing."""

        self._logger.debug("Rolling back streamer %d after streaming, highest ack from streaming subsystem was %d", index, highest_ack)
        self.acknowledge_streamer(index, highest_ack, False)

    def process_streamers(self):
        """Check if any streamers should be handed to the stream manager."""

        # Check for any triggered streamers and pass them to stream manager
        in_progress = self._stream_manager.in_progress()
        triggered = self.graph.check_streamers(blacklist=in_progress)

        for streamer in triggered:
            self._stream_manager.process_streamer(streamer, callback=self._handle_streamer_finished)

    def trigger_streamer(self, index):
        """Pass a streamer to the stream manager if it has data."""

        self._logger.debug("trigger_streamer RPC called on streamer %d", index)

        if index >= len(self.graph.streamers):
            return _pack_sgerror(SensorGraphError.STREAMER_NOT_ALLOCATED)

        if index in self._stream_manager.in_progress():
            return _pack_sgerror(SensorGraphError.STREAM_ALREADY_IN_PROGRESS)

        streamer = self.graph.streamers[index]
        if not streamer.triggered(manual=True):
            return _pack_sgerror(SensorGraphError.STREAMER_HAS_NO_NEW_DATA)

        self._logger.debug("calling mark_streamer on streamer %d from trigger_streamer RPC", index)
        self.graph.mark_streamer(index)

        self.process_streamers()

        return Error.NO_ERROR

    def count_nodes(self):
        """Count the number of nodes."""

        return len(self.graph.nodes)

    def persist(self):
        """Trigger saving the current sensorgraph to persistent storage."""

        self.persisted_nodes = self.graph.dump_nodes()
        self.persisted_streamers = self.graph.dump_streamers()
        self.persisted_exists = True
        self.persisted_constants = self._sensor_log.dump_constants()

    def reset(self):
        """Clear the sensorgraph from RAM and flash."""

        self.persisted_exists = False
        self.persisted_nodes = []
        self.persisted_streamers = []
        self.persisted_constants = []
        self.graph.clear()

        self.streamer_status = {}

    def add_node(self, binary_descriptor):
        """Add a node to the sensor_graph using a binary node descriptor.

        Args:
            binary_descriptor (bytes): An encoded binary node descriptor.

        Returns:
            int: A packed error code.
        """

        try:
            node_string = parse_binary_descriptor(binary_descriptor)
        except:
            self._logger.exception("Error parsing binary node descriptor: %s", binary_descriptor)
            return _pack_sgerror(SensorGraphError.INVALID_NODE_STREAM)  # FIXME: Actually provide the correct error codes here

        try:
            self.graph.add_node(node_string)
        except NodeConnectionError:
            return _pack_sgerror(SensorGraphError.STREAM_NOT_IN_USE)
        except ProcessingFunctionError:
            return _pack_sgerror(SensorGraphError.INVALID_PROCESSING_FUNCTION)
        except ResourceUsageError:
            return _pack_sgerror(SensorGraphError.NO_NODE_SPACE_AVAILABLE)

        return Error.NO_ERROR

    def add_streamer(self, binary_descriptor):
        """Add a streamer to the sensor_graph using a binary streamer descriptor.

        Args:
            binary_descriptor (bytes): An encoded binary streamer descriptor.

        Returns:
            int: A packed error code
        """

        streamer = streamer_descriptor.parse_binary_descriptor(binary_descriptor)

        try:
            self.graph.add_streamer(streamer)
            self.streamer_status[len(self.graph.streamers) - 1] = StreamerStatus()

            return Error.NO_ERROR
        except ResourceUsageError:
            return _pack_sgerror(SensorGraphError.NO_MORE_STREAMER_RESOURCES)

    def inspect_streamer(self, index):
        """Inspect the streamer at the given index."""

        if index >= len(self.graph.streamers):
            return [_pack_sgerror(SensorGraphError.STREAMER_NOT_ALLOCATED), b'\0'*14]

        return [Error.NO_ERROR, streamer_descriptor.create_binary_descriptor(self.graph.streamers[index])]

    def inspect_node(self, index):
        """Inspect the graph node at the given index."""

        if index >= len(self.graph.nodes):
            raise RPCErrorCode(6)  #FIXME: use actual error code here for UNKNOWN_ERROR status

        return create_binary_descriptor(str(self.graph.nodes[index]))

    def query_streamer(self, index):
        """Query the status of the streamer at the given index."""

        if index >= len(self.graph.streamers):
            return None

        info = self.streamer_status[index]
        highest_ack = self.streamer_acks.get(index, 0)

        return [info.last_attempt_time, info.last_success_time, info.last_error, highest_ack, info.last_status, info.attempt_number, info.comm_status]


class SensorGraphMixin(object):
    """Mixin for an IOTileController that implements the sensor-graph subsystem.

    Args:
        sensor_log (SensorLog): The rsl subsystem.
        stream_man (StreamManager): The stream manager subsystem
        model (DeviceModel): A device model containing resource limits about the
            emulated device.
    """

    def __init__(self, emulator, sensor_log, stream_manager, model):
        self.sensor_graph = SensorGraphSubsystem(sensor_log, stream_manager, model, emulator, executor=EmulatedRPCExecutor(self._device))
        self._post_config_subsystems.append(self.sensor_graph)

    @tile_rpc(*rpcs.SG_COUNT_NODES)
    def sg_count_nodes(self):
        """Count the number of nodes in the sensor_graph."""

        return [self.sensor_graph.count_nodes()]

    @tile_rpc(*rpcs.SG_ADD_NODE)
    def sg_add_node(self, descriptor):
        """Add a node to the sensor_graph using its binary descriptor."""

        err = self.sensor_graph.add_node(descriptor)
        return [err]

    @tile_rpc(*rpcs.SG_SET_ONLINE)
    def sg_set_online(self, online):
        """Set the sensor-graph online/offline."""

        self.sensor_graph.enabled = bool(online)
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.SG_GRAPH_INPUT)
    def sg_graph_input(self, value, stream_id):
        """"Present a graph input to the sensor_graph subsystem."""

        self.sensor_graph.process_input(stream_id, value)
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.SG_RESET_GRAPH)
    def sg_reset_graph(self):
        """Clear the in-memory and persisted graph (if any)."""
        self.sensor_graph.reset()
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.SG_PERSIST_GRAPH)
    def sg_persist_graph(self):
        """Save the current in-memory graph persistently."""

        self.sensor_graph.persist()
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.SG_INSPECT_GRAPH_NODE)
    def sg_inspect_graph_node(self, index):
        """Inspect the given graph node."""

        desc = self.sensor_graph.inspect_node(index)
        return [desc]

    @tile_rpc(*rpcs.SG_ADD_STREAMER)
    def sg_add_streamer(self, desc):
        """Add a graph streamer using a binary descriptor."""

        if len(desc) == 13:
            desc += b'\0'

        err = self.sensor_graph.add_streamer(desc)
        return [err]

    @tile_rpc(*rpcs.SG_INSPECT_STREAMER)
    def sg_inspect_streamer(self, index):
        """Inspect a sensorgraph streamer by index."""

        return self.sensor_graph.inspect_streamer(index)

    @tile_rpc(*rpcs.SG_TRIGGER_STREAMER)
    def sg_trigger_streamer(self, index):
        """Manually trigger a streamer."""

        err = self.sensor_graph.trigger_streamer(index)

        return [err]

    @tile_rpc(*rpcs.SG_SEEK_STREAMER)
    def sg_seek_streamer(self, index, force, value):
        """Ackowledge a streamer."""

        force = bool(force)
        err = self.sensor_graph.acknowledge_streamer(index, value, force)
        return [err]

    @tile_rpc(*rpcs.SG_QUERY_STREAMER)
    def sg_query_streamer(self, index):
        """Query the current status of a streamer."""

        resp = self.sensor_graph.query_streamer(index)
        if resp is None:
            return [struct.pack("<L", _pack_sgerror(SensorGraphError.STREAMER_NOT_ALLOCATED))]

        return [struct.pack("<LLLLBBBx", *resp)]


async def process_graph_input(graph, stream, value, rpc_executor):
    """Process an input through this sensor graph.

    The tick information in value should be correct and is transfered
    to all results produced by nodes acting on this tick.  This coroutine
    is an asyncio compatible version of SensorGraph.process_input()

    Args:
        stream (DataStream): The stream the input is part of
        value (IOTileReading): The value to process
        rpc_executor (RPCExecutor): An object capable of executing RPCs
            in case we need to do that.
    """

    graph.sensor_log.push(stream, value)

    # FIXME: This should be specified in our device model
    if stream.important:
        associated_output = stream.associated_stream()
        graph.sensor_log.push(associated_output, value)

    to_check = deque([x for x in graph.roots])

    while len(to_check) > 0:
        node = to_check.popleft()
        if node.triggered():
            try:
                results = node.process(rpc_executor, graph.mark_streamer)
                for result in results:
                    if inspect.iscoroutine(result.value):
                        result.value = await asyncio.ensure_future(result.value)

                    result.raw_time = value.raw_time
                    graph.sensor_log.push(node.stream, result)
            except:
                logging.getLogger(__name__).exception("Unhandled exception in graph node processing function for node %s", str(node))

            # If we generated any outputs, notify our downstream nodes
            # so that they are also checked to see if they should run.
            if len(results) > 0:
                to_check.extend(node.outputs)
