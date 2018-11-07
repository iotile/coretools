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
"""

import threading
import logging
from builtins import range
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.reports import IOTileReading
from iotile.sg import DataStream, DataStreamSelector, SensorGraph
from iotile.sg.node_descriptor import parse_binary_descriptor
from iotile.sg.exceptions import NodeConnectionError, ProcessingFunctionError, ResourceUsageError
from ...constants import rpcs, pack_error, Error, ControllerSubsystem, streams, SensorGraphError

def _pack_sgerror(short_code):
    """Pack a short error code with the sensorgraph subsystem."""

    return pack_error(ControllerSubsystem.SENSOR_GRAPH, short_code)


class SensorGraphSubsystem(object):
    """Container for sensor graph state.

    There is a distinction between which sensor-graph is saved into persisted
    storage vs currently loaded and running.
    """

    def __init__(self, model, sensor_log):
        self._model = model
        self._mutex = threading.Lock()
        self._sensor_log = sensor_log
        self._logger = logging.getLogger(__name__)
        self.graph = SensorGraph(sensor_log, model=model)

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

    def persist(self):
        """Trigger saving the current sensorgraph to persistent storage."""

        with self._mutex:
            self.persisted_nodes = self.graph.dump_nodes()
            self.peristed_streamers = self.graph.dump_streamers()
            self.persisted_exists = True
            self.peristed_constants = self._sensor_log.dump_constants()

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
