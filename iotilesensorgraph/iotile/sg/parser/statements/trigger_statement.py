"""Copy stream statement."""

from builtins import str
from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ...stream import DataStream


@python_2_unicode_compatible
class TriggerStatement(SensorGraphStatement):
    """Trigger a streamer

    The form of the statement should be
    trigger streamer <index>

    That streamer is manually triggered.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        self.index = parsed['index']

        super(TriggerStatement, self).__init__([], location)

    def __str__(self):
        return u'trigger streamer {};'.format(self.index)

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This adds a single node to the sensor graph with the trigger_streamer function
        as is processing function.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]
        alloc = parent.allocator

        # The output is unused
        output = alloc.allocate_stream(DataStream.UnbufferedType, attach=True)

        trigger_stream, trigger_cond = parent.trigger_chain()
        streamer_const = alloc.allocate_stream(DataStream.ConstantType, attach=True)

        sensor_graph.add_node(u"({} {} && {} always) => {} using trigger_streamer".format(trigger_stream, trigger_cond, streamer_const, output))
        sensor_graph.add_constant(streamer_const, self.index)
