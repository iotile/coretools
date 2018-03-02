"""Call RPC statement."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ...stream import DataStream


@python_2_unicode_compatible
class CallRPCStatement(SensorGraphStatement):
    """Call an RPC on a tile.

    The form of the statement should be
    call (ident|number) on slot_id => stream

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        self.rpc_id = parsed[0]
        self.slot_id = parsed[1]

        self.stream = None
        if 'explicit_stream' in parsed:
            self.stream = parsed['explicit_stream'][0]

        super(CallRPCStatement, self).__init__([], location)

    def __str__(self):
        if self.stream is not None:
            return u'call 0x%X on %s => %s;' % (self.rpc_id, str(self.slot_id), str(self.stream))

        return u'call 0x%X on %s;' % (self.rpc_id, str(self.slot_id))

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This adds a single node to the sensor graph with the call_rpc function
        as is processing function.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]
        alloc = parent.allocator

        trigger_stream, trigger_cond = parent.trigger_chain()
        rpc_const = alloc.allocate_stream(DataStream.ConstantType, attach=True)
        rpc_val = (self.slot_id.address << 16) | self.rpc_id

        stream = self.stream
        if stream is None:
            stream = alloc.allocate_stream(DataStream.UnbufferedType)

        sensor_graph.add_node(u"({} {} && {} always) => {} using call_rpc".format(trigger_stream, trigger_cond, rpc_const, stream))
        sensor_graph.add_constant(rpc_const, rpc_val)

