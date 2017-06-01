"""Sensor Graph main object."""

from collections import deque
from pkg_resources import iter_entry_points
from .node_descriptor import parse_node_descriptor
from .slot import SlotIdentifier
from .known_constants import config_user_tick_secs
from .exceptions import NodeConnectionError, ProcessingFunctionError
from iotile.core.exceptions import ArgumentError


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
        self.constant_database = {}
        self.config_database = {}
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

    def add_config(self, slot, config_id, config_type, value):
        """Add a config variable assignment to this sensor graph.

        Args:
            slot (SlotIdentifier): The slot identifier that this config
                variable is assigned to.
            config_id (int): The 16-bit id of this config_id
            config_type (str): The type of the config variable, currently
                supported are fixed width integer types and strings
            value (str|int): The value to assign to the config variable.
        """

        if slot not in self.config_database:
            self.config_database[slot] = {}

        self.config_database[slot][config_id] = (config_type, value)

    def add_constant(self, stream, value):
        """Store a constant value for use in this sensor graph.

        Constant assignments occur after all sensor graph nodes have been
        allocated since they must be propogated to all appropriate virtual
        stream walkers.

        Args:
            stream (DataStream): The constant stream to assign the value to
            value (int): The value to assign.
        """

        if stream in self.constant_database:
            raise ArgumentError("Attempted to set the same constant twice", stream=stream, old_value=self.constant_database[stream], new_value=value)

        self.constant_database[stream] = value

    def get_config(self, slot, config_id):
        """Get a config variable assignment previously set on this sensor graph.

        Args:
            slot (SlotIdentifier): The slot that we are setting this config variable
                on.
            config_id (int): The 16-bit config variable identifier.

        Returns:
            (str, str|int): Returns a tuple with the type of the config variable and
                the value that is being set.

        Raises:
            ArgumentError: If the config variable is not currently set on the specified
                slot.
        """

        if slot not in self.config_database:
            raise ArgumentError("No config variables have been set on specified slot", slot=slot)

        if config_id not in self.config_database[slot]:
            raise ArgumentError("Config variable has not been set on specified slot", slot=slot, config_id=config_id)

        return self.config_database[slot][config_id]

    def user_tick(self):
        """Check the config variables to see if there is a user tick.

        Sensor Graph has a built-in 10 second tick that is sent every 10 seconds
        to allow for triggering timed events.  Users can also set up another tick
        at a different, usually faster interval for their own purposes.

        This is done by setting a config variable on the controller with the desired
        tick interval, which is then interpreted by this function.

        The appropriate config_id to use is listed in known_constants.py

        Returns:
            int: 0 if the user tick is disabled, otherwise the number of seconds
                between each tick
        """

        slot = SlotIdentifier.FromString('controller')

        try:
            var = self.get_config(slot, config_user_tick_secs)
            return var[1]
        except ArgumentError:
            return 0

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

    def dump_nodes(self):
        """Dump all of the nodes in this sensor graph as a list of strings."""

        return [str(x) for x in self.nodes]
