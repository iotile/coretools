"""Blocks that execute when someone is connected."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ...known_constants import user_connected, user_disconnected
from ...node import InputTrigger
from ...stream import DataStream
from ..scopes import GatedClockScope


@python_2_unicode_compatible
class WhenBlock(SensorGraphStatement):
    """A block of statements that should run when someone is connected to the device.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this when block.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, children, location=None):
        self.slot_id = parsed[0]

        super(WhenBlock, self).__init__(children, location)

    def __str__(self):
        return u"when connected to %s" % (str(self.slot_id),)

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

        # We want to create a gated clock that only fires when there is a connection
        # to a communication tile.  So we create a latching constant stream that is used to gate the
        # clock passed through from the previous scope.
        connect_stream = alloc.allocate_stream(DataStream.UnbufferedType, attach=True)
        disconnect_stream = alloc.allocate_stream(DataStream.UnbufferedType, attach=True)
        latch_stream = alloc.allocate_stream(DataStream.ConstantType, attach=True)
        latch_on_stream = alloc.allocate_stream(DataStream.ConstantType, attach=True)
        latch_off_stream = alloc.allocate_stream(DataStream.ConstantType, attach=True)

        sensor_graph.add_node(u"({} always) => {} using copy_latest_a".format(user_connected, connect_stream))
        sensor_graph.add_node(u"({} always) => {} using copy_latest_a".format(user_disconnected, disconnect_stream))

        sensor_graph.add_node(u"({} always && {} when value=={}) => {} using copy_latest_a".format(latch_on_stream, connect_stream, self.slot_id.address, latch_stream))
        sensor_graph.add_node(u"({} always && {} when value=={}) => {} using copy_latest_a".format(latch_off_stream, disconnect_stream, self.slot_id.address, latch_stream))

        sensor_graph.add_constant(latch_on_stream, 1)
        sensor_graph.add_constant(latch_off_stream, 0)
        sensor_graph.add_constant(latch_stream, 0)

        new_scope = GatedClockScope(sensor_graph, scope_stack, (latch_stream, InputTrigger(u'value', u'==', 1)))

        # Add two new identifiers to the scope for supporting on connect and on disconnect events
        new_scope.add_identifier('connect', connect_stream)
        new_scope.add_identifier('disconnect', disconnect_stream)
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
