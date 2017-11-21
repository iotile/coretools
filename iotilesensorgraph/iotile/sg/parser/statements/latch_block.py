"""Blocks that gate child execution on a condition."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ...node import InputTrigger
from ...stream import DataStream
from ..scopes import ClockScope


@python_2_unicode_compatible
class LatchBlock(SensorGraphStatement):
    """A block of statements that should run when a latch is true.

    The when block is a specific kind of latch block that gates its statements
    on when someone is connected.  The Latch block more generally lets you gate
    on any stream trigger condition.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this when block.
    """

    def __init__(self, parsed, children):
        cond = parsed[0]
        trigger_type = cond[0]
        stream = cond[1]
        oper = cond[2]
        ref = cond[3]

        trigger = InputTrigger(trigger_type, oper, ref)
        self.stream = stream
        self.trigger = trigger

        super(LatchBlock, self).__init__(children)

    def __str__(self):
        return u"when " + self.trigger.format_trigger(self.stream)

    def execute_before(self, sensor_graph, scope_stack):
        """Execute statement before children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]
        alloc = parent.allocator

        # We want to create a gated clock that only fires when the latching constant is true
        clock_stream = alloc.allocate_stream(DataStream.CounterType)  # Don't attach because it's not an input anywhere

        parent_clock = parent.clock(1)

        sensor_graph.add_node(u"({} {} && {} {}) => {} using copy_latest_a".format(parent_clock[0], parent_clock[1], self.stream, self.trigger, clock_stream))
        sensor_graph.add_constant(self.stream, 0)

        new_scope = ClockScope(sensor_graph, scope_stack, (clock_stream, InputTrigger(u'count', u'==', 1)), 1)
        scope_stack.append(new_scope)

    def execute_after(self, sensor_graph, scope_stack):
        """Execute statement after children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        scope_stack.pop()
