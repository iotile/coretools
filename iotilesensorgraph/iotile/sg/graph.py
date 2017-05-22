"""Sensor Graph main object."""


class SensorGraph(object):
    """A graph based data processing engine."""

    def __init__(self, model=None):
        self.roots = []
        self.nodes = []
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


