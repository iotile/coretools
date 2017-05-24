"""Sensor Graph main object."""

from collections import deque
from pkg_resources import iter_entry_points
from .node_descriptor import parse_node_descriptor
from .exceptions import NodeConnectionError, ProcessingFunctionError


class SensorGraph(object):
    """A graph based data processing engine.

    Args:
        sensor_log (SensorLog): The sensor log where we should store our
            data
        model (DeviceModel): The device model to use for limiting our
            available resources
    """

    def __init__(self, sensor_log, model=None):
        self.roots = []
        self.nodes = []
        self.sensor_log = sensor_log
        self.model = model

    def add_node(self, node_descriptor):
        """Add a node to the sensor graph based on the description given.

        The node_descriptor must follow the sensor graph DSL and describe
        a node whose input nodes already exist.

        Args:
            node_descriptor (str): A description of the node to be added
                including its inputs, triggering conditions, processing function
                and output stream.
        """

        node, inputs, processor = parse_node_descriptor(node_descriptor, self.model)

        for i, input_data in enumerate(inputs):
            selector, trigger = input_data

            walker = self.sensor_log.create_walker(selector)
            node.connect_input(i, walker, trigger)

            if selector.input:
                self.roots.append(node)
            else:
                found = False
                for other in self.nodes:
                    if selector.matches(other.stream):
                        other.connect_output(node)
                        found = True

                if not found and selector.buffered:
                    raise NodeConnectionError("Node has input that refers to another node that has not been created yet", node_descriptor=node_descriptor, input_selector=str(selector), input_index=i)

        # Find and load the processing function for this node
        func = self._find_processing_function(processor)
        if func is None:
            raise ProcessingFunctionError("Could not find processing function in installed packages", func_name=processor)

        node.set_func(processor, func)
        self.nodes.append(node)

    def process_input(self, stream, value, rpc_executor):
        """Process an input through this sensor graph.

        Args:
            stream (DataStream): The stream the input is part of
            value (IOTileReading): The value to process
            rpc_executor (RPCExecutor): An object capable of executing RPCs
                in case we need to do that.
        """

        self.sensor_log.push(stream, value)

        to_check = deque([x for x in self.roots])

        while len(to_check) > 0:
            node = to_check.popleft()
            if node.triggered():
                results = node.process(rpc_executor)
                for result in results:
                    self.sensor_log.push(node.stream, result)

                # If we generated any outputs, notify our downstream nodes
                # so that they are also checked to see if they should run.
                if len(results) > 0:
                    to_check.extend(node.outputs)

    @classmethod
    def _find_processing_function(cls, name):
        """Find a processing function by name.

        This function searches through installed processing functions
        using pkg_resources.

        Args:
            name (str): The name of the function we're looking for

        Returns:
            callable: The processing function
        """

        for entry in iter_entry_points(u'iotile.sg_processor', name):
            return entry.load()
