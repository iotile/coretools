"""Copy stream statement."""

from builtins import str
from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ...stream import DataStream


@python_2_unicode_compatible
class CopyStatement(SensorGraphStatement):
    """Copy one stream into another

    The form of the statement should be
    copy [all | count | average] [stream | number] => <output stream>

    If stream is passed, it is the stream that is copied when the current
    scope's trigger fires.  Otherwise the trigger value is copied.

    You can also copy a fixed constant value by passing an explicit number.

    If all or count are specified all readings are copied or the count
    of the number of readings is copied instead of just the latest reading.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        self.all = 'modifier' in parsed and parsed['modifier'] == u'all'
        self.count = 'modifier' in parsed and parsed['modifier'] == u'count'
        self.average = 'modifier' in parsed and parsed['modifier'] == u'average'

        self.explicit_input = None
        if 'explicit_input' in parsed:
            self.explicit_input = parsed['explicit_input'][0]

        self.constant_input = None
        if 'constant_input' in parsed:
            self.constant_input = parsed['constant_input']

        self.output = parsed['output'][0]

        super(CopyStatement, self).__init__([], location)

    def __str__(self):
        op = u'copy'

        if self.all:
            op = u'copy all'
        elif self.average:
            op = u'copy average'
        elif self.count:
            op = u'copy count'

        input_stream = u""
        if self.explicit_input:
            input_stream = u' ' + str(self.explicit_input)
        elif self.constant_input is not None:
            input_stream = u' ' + str(self.constant_input)

        return u'{}{} => {};'.format(op, input_stream, self.output)

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This adds a single node to the sensor graph with either the
        copy_latest_a, copy_all_a or average_a function as is processing function.

        If there is an explicit stream passed, that is used as input a with the
        current scope's trigger as input b, otherwise the current scope's trigger
        is used as input a.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]
        alloc = parent.allocator

        trigger_stream, trigger_cond = parent.trigger_chain()

        op = 'copy_latest_a'
        if self.all:
            op = 'copy_all_a'
        elif self.average:
            op = 'average_a'
        elif self.count:
            op = 'copy_count_a'

        if self.explicit_input:
            sensor_graph.add_node(u"({} always && {} {}) => {} using {}".format(self.explicit_input, trigger_stream, trigger_cond, self.output, op))
        elif self.constant_input is not None:
            const_stream = alloc.allocate_stream(DataStream.ConstantType, attach=True)

            sensor_graph.add_node(u"({} always && {} {}) => {} using {}".format(const_stream, trigger_stream, trigger_cond, self.output, op))
            sensor_graph.add_constant(const_stream, self.constant_input)
        else:
            sensor_graph.add_node(u"({} {}) => {} using {}".format(trigger_stream, trigger_cond, self.output, op))
