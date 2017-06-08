from ...node import InputTrigger
from ...stream import DataStream
from ...exceptions import SensorGraphSemanticError
from .scope import Scope


class ClockScope(Scope):
    """A scope that implements trigger_chain and can provide a clock.

    Args:
        sensor_graph (SensorGraph): The sensor graph we are working on.
        scope_stack (list(Scope)): The stack of already allocated scopes.
        clock_input ((DataStream, InputTrigger)): The input clock stream
            and trigger conditions used to create this clock.
        interval (int): The interval at which the input clock stream gets
            updated in seconds.
    """

    def __init__(self, sensor_graph, scope_stack, clock_input, interval):
        parent = scope_stack[-1]
        alloc = parent.allocator
        sensor_graph = parent.sensor_graph

        super(ClockScope, self).__init__(u"Sub-Clock Scope", sensor_graph, alloc, parent)

        # Create our own node to create our clock chain
        # this will be optimized out if it turned out not to be needed
        # after all nodes have been allocated
        stream = alloc.allocate_stream(DataStream.CounterType)
        sensor_graph.add_node(u'({} {}) => {} using copy_all_a'.format(clock_input[0], clock_input[1], stream))

        self.clock_stream = stream
        self.clock_interval = interval

    def clock(self, interval):
        """Return a NodeInput tuple for triggering an event every interval.

        Args:
            interval (int): The interval (in seconds) at which this input should
                trigger.
        """

        if (interval % self.clock_interval) != 0:
            raise SensorGraphSemanticError("ClockScope was asked for a clock that was not a multiple of its internal clock", internal_interval=self.clock_interval, requested_interval=interval)

        stream = self.allocator.attach_stream(self.clock_stream)

        return (stream, InputTrigger(u'count', '==', interval // self.clock_interval))

