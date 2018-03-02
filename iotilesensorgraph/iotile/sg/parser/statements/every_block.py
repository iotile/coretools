"""Time based event block for scheduling RPCs every X interval."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ..scopes import TriggerScope

@python_2_unicode_compatible
class EveryBlock(SensorGraphStatement):
    """A block of statements that should run every time interval

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this every block.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, children, location=None):
        self.interval = parsed[0]
        self.basis = parsed[1]

        super(EveryBlock, self).__init__(children, location)

    def __str__(self):
        if self.basis == 'system':
            return u"every %s" % (str(self.interval),)

        return u"every %d %s" % (self.interval, self.basis)

    def execute_before(self, sensor_graph, scope_stack):
        """Execute statement before children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]
        new_scope = TriggerScope(sensor_graph, scope_stack, parent.clock(self.interval, basis=self.basis))
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
