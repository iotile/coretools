from .scope import Scope
from ..exceptions import SensorGraphSemanticError


class RootScope(Scope):
    """The global scope that contains all others.

    Args:
        sensor_graph (SensorGraph): The SensorGraph we
            are operating on.
    """

    def __init__(self, sensor_graph, clock_node):
        super(RootScope, self).__init__(u"Root Scope", sensor_graph, None)

    def trigger_chain(self):
        """Return a NodeInput tuple for creating a node.

        Returns:
            (StreamIdentifier, InputTrigger)
        """

        raise SensorGraphSemanticError("There is no trigger chain in the root scope since no triggering criteria have been set")

    def clock(self, interval):
        """Return a NodeInput tuple for triggering an event every interval.

        Args:
            interval (int): The interval (in seconds) at which this input should
                trigger.
        """
