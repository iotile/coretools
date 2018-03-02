from .scope import Scope
from ...node import InputTrigger
from ...exceptions import SensorGraphSemanticError
from ...stream import DataStream

class TriggerScope(Scope):
    """A scope that implements trigger_chain but cannot provide a clock.

    Args:
        sensor_graph (SensorGraph): The sensor graph we are working on.
        scope_stack (list(Scope)): The stack of already allocated scopes.
        trigger_input ((DataStream, InputTrigger): The input trigger stream
            and condition.  The input trigger must already be attached.
    """

    def __init__(self, sensor_graph, scope_stack, trigger_input):
        parent = scope_stack[-1]
        alloc = parent.allocator
        sensor_graph = parent.sensor_graph

        super(TriggerScope, self).__init__(u"Trigger Scope", sensor_graph, alloc, parent)

        # Create our own node to create our triggering chain
        # this will be optimized out if it turned out not to be needed
        # after all nodes have been allocated.  Since we can trigger on a root
        # node, make sure we don't try to make our output a root input.
        stream_type = trigger_input[0].stream_type
        if stream_type == DataStream.InputType:
            stream_type = DataStream.UnbufferedType

        stream = alloc.allocate_stream(stream_type)
        sensor_graph.add_node(u'({} {}) => {} using copy_latest_a'.format(trigger_input[0], trigger_input[1], stream))
        self.trigger_stream = stream
        self.trigger_cond = InputTrigger(u'count', '==', 1)

    def trigger_chain(self):
        """Return a NodeInput tuple for creating a node.

        Returns:
            (StreamIdentifier, InputTrigger)
        """

        trigger_stream = self.allocator.attach_stream(self.trigger_stream)
        return (trigger_stream, self.trigger_cond)

    def clock(self, interval, basis):
        """Return a NodeInput tuple for triggering an event every interval.

        We request each distinct type of clock at most once and combine it with our
        latch stream each time it is requested.

        Args:
            interval (int): The interval (in seconds) at which this input should
                trigger.
        """

        raise SensorGraphSemanticError("TriggerScope does not provide a clock output that can be used.")
