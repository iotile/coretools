"""On blocks trigger functions when an event occurs on a stream."""

from builtins import str
from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ...node import InputTrigger

@python_2_unicode_compatible
class OnBlock(SensorGraphStatement):
    """A block of statements that should run every time an event occurs

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this on block.
    """

    def __init__(self, parsed, children):
        cond = parsed[0]

        self.named_event = None
        self.explicit_stream = None
        self.explcit_trigger = None

        # Identifier parse tree is Group(Identifier)
        if cond.getName() == 'identifier':
            self.named_event = cond[0][0]
        elif cond.getName() == 'stream_trigger':
            trigger_type = cond[0][0]
            stream = cond[0][1]
            oper = cond[0][2]
            ref = cond[0][3]

            trigger = InputTrigger(trigger_type, oper, ref)
            self.explicit_stream = stream
            self.explicit_trigger = trigger

        super(OnBlock, self).__init__(children)

    def __str__(self):
        return u"on %s" % (str(self.ident_or_stream),)

    def execute_before(self, sensor_graph, scope_stack):
        """Execute statement before children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]

        new_scope = TriggerScope(sensor_graph, scope_stack, parent.clock(self.interval))
        scope_stack.append(new_scope)
