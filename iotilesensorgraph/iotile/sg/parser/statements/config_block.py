"""Configuration block for assigning config variables to a tile."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ..scopes.scope import Scope


@python_2_unicode_compatible
class ConfigBlock(SensorGraphStatement):
    """A block of config variables to assign to a tile.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this config block.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, children, location=None):
        self.slot = parsed[0]

        super(ConfigBlock, self).__init__(children, location)

    def __str__(self):
        return u"config {}".format(self.slot)

    def execute_before(self, sensor_graph, scope_stack):
        """Execute statement before children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]
        new_scope = Scope("Configuration Scope", sensor_graph, parent.allocator, parent)
        new_scope.add_identifier('current_slot', self.slot)
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
