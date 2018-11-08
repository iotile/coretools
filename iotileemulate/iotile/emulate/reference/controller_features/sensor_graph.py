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
  - [ ] Add SG_QUERY_STREAMER
  - [ ] Add SG_ADD_STREAMER
  - [ ] Add SG_TRIGGER_STREAMER
  - [ ] Add SG_INSPECT_STREAMER
  - [ ] Add SG_SEEK_STREAMER
  - [ ] Add dump/restore support
  - [ ] Properly initialize all constant streams to 0
"""

import logging
from builtins import range
from iotile.core.hw.virtual import tile_rpc, RPCErrorCode
from iotile.core.hw.reports import IOTileReading
from iotile.sg import DataStream, DataStreamSelector, SensorGraph
from iotile.sg.node_descriptor import parse_binary_descriptor, create_binary_descriptor
from iotile.sg.exceptions import NodeConnectionError, ProcessingFunctionError, ResourceUsageError
from ...constants import rpcs, pack_error, Error, ControllerSubsystem, streams, SensorGraphError

def _pack_sgerror(short_code):
    """Pack a short error code with the sensorgraph subsystem."""

    return pack_error(ControllerSubsystem.SENSOR_GRAPH, short_code)


class SensorGraphSubsystem(object):
    """Container for sensor graph state.

    There is a distinction between which sensor-graph is saved into persisted
    storage vs currently loaded and running.  This subsystem needs to be
    created with a shared mutex with the sensor_log subsystem to make sure
    all accesses are properly synchronized.
    """

    def __init__(self, model, sensor_log, mutex):
        self._model = model
        self._mutex = mutex
        self._sensor_log = sensor_log
        self._logger = logging.getLogger(__name__)
        self.graph = SensorGraph(sensor_log, model=model, enforce_limits=True)

        self.persisted_exists = False
        self.persisted_nodes = []
        self.persisted_streamers = []
        self.persisted_constants = []

        self.enabled = False

    def clear_to_reset(self, _config_vars):
        """Clear all volatile information across a reset.

        The reset behavior is that:
        - any persisted sensor_graph is loaded
        - if there is a persisted graph found, enabled is set to True
        - if there is a persisted graph found, reset readings are pushed
          into it.
        """

        with self._mutex:
            self.graph.clear()

            if not self.persisted_exists:
                return

            for node in self.persisted_nodes:
                self.graph.add_node(node)

            #FIXME: Also add in streamers

            # Load in the constants
            for stream, reading in self.persisted_constants:
                self._sensor_log.push(stream, reading)

            self.enabled = True

            #FIXME: queue sending reset readings

    def process_input(self, encoded_stream, value):
        """Process or drop a graph input.

        This must not be called directly from an RPC but always via a deferred
        task.
        """

        if not self.enabled:
            return

        stream = DataStream.FromEncoded(encoded_stream)

        # FIXME: Tag this with the current timestamp
        reading = IOTileReading(encoded_stream, 0, value)

        with self._mutex:
            self.graph.process_input(stream, reading, None)  #FIXME: add in an rpc executor for this device.

    def count_nodes(self):
        """Count the number of nodes."""

        with self._mutex:
            return len(self.graph.nodes)

    def persist(self):
        """Trigger saving the current sensorgraph to persistent storage."""

        with self._mutex:
            self.persisted_nodes = self.graph.dump_nodes()
            self.persisted_streamers = self.graph.dump_streamers()
            self.persisted_exists = True
            self.persisted_constants = self._sensor_log.dump_constants()

    def reset(self):
        """Clear the sensorgraph from RAM and flash."""

        with self._mutex:
            self.persisted_exists = False
            self.persisted_nodes = []
            self.persisted_streamers = []
            self.persisted_constants = []
            self.graph.clear()

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

    def inspect_node(self, index):
        """Inspect the graph node at the given index."""

        with self._mutex:
            if index >= len(self.graph.nodes):
                raise RPCErrorCode(6)  #FIXME: use actual error code here for UNKNOWN_ERROR status

            return create_binary_descriptor(str(self.graph.nodes[index]))


class SensorGraphMixin(object):
    """Mixin for an IOTileController that implements the sensor-graph subsystem.

    Args:
        sensor_log (SensorLog): The storage area that should be used for storing
            readings.
        model (DeviceModel): A device model containing resource limits about the
            emulated device.
        mutex (threading.Lock): A shared mutex from the sensor_log subsystem to
            use to make sure we only access it from a single thread at a time.
    """

    def __init__(self, sensor_log, model, mutex):
        self.sensor_graph = SensorGraphSubsystem(model, sensor_log, mutex)
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

        self._device.deferred_task(self.sensor_graph.process_input, stream_id, value)
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
