"""Subtract input B from input A statement."""

from __future__ import (unicode_literals, print_function, absolute_import)
from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from iotile.sg.exceptions import SensorGraphSemanticError
from ...stream import DataStream


@python_2_unicode_compatible
class SubtractStatement(SensorGraphStatement):
    """Subtract the two input values

    The form of the statement should be
    subtract stream => stream[, default value];

    Where the default value is optional and is used to initialize the
    constant stream.  If it is not passed it defaults to 0.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        self.subtract_stream = parsed[0]
        self.stream = parsed[1]
        self.default = None

        if 'default' in parsed:
            self.default = parsed['default']

        super(SubtractStatement, self).__init__([], location)

    def __str__(self):
        default = u""
        if self.default is not None:
            default = ", default %d" % self.default

        return 'subtract {} => {}{};'.format(self.subtract_stream, self.stream, default)

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This adds a single node to the sensor graph with subtract as the function
        so that the current scope's trigger stream has the subtract_stream's value
        subtracted from it.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        if self.subtract_stream.stream_type != DataStream.ConstantType:
            raise SensorGraphSemanticError("You can only subtract a constant value currently", stream=self.subtract_stream)

        parent = scope_stack[-1]
        alloc = parent.allocator

        trigger_stream, trigger_cond = parent.trigger_chain()

        sensor_graph.add_node(u"({} always && {} {}) => {} using {}".format(self.subtract_stream, trigger_stream, trigger_cond, self.stream, 'subtract_a_from_b'))

        value = self.default
        if value is None:
            value = 0

        if self.default is not None and self.subtract_stream in sensor_graph.constant_database:
            raise SensorGraphSemanticError("Attempted to set the same constant stream twice", stream=self.subtract_stream, new_value=self.default)
        elif self.default is None and self.subtract_stream in sensor_graph.constant_database:
            return

        sensor_graph.add_constant(self.subtract_stream, value)
