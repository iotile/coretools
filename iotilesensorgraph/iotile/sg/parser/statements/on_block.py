"""On blocks trigger functions when an event occurs on a stream."""

from builtins import str
from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ..scopes import TriggerScope
from ...node import InputTrigger, TrueTrigger
from ... import DataStream
from iotile.core.exceptions import ArgumentError


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
            self.named_event = cond[0]
        elif cond.getName() == 'stream_trigger':
            trigger_type = cond[0]
            stream = cond[1]
            oper = cond[2]
            ref = cond[3]

            trigger = InputTrigger(trigger_type, oper, ref)
            self.explicit_stream = stream
            self.explicit_trigger = trigger
        elif cond.getName() == 'stream_always':
            stream = cond[0]
            trigger = TrueTrigger()
            self.explicit_stream = stream
            self.explicit_trigger = trigger
        else:
            raise ArgumentError("OnBlock created from an invalid ParseResults object", parse_results=parsed)

        super(OnBlock, self).__init__(children)

    def __str__(self):
        if self.explicit_stream is not None:
            return u"on " + self.explicit_trigger.format_trigger(self.explicit_stream)

        return u"on {}".format(self.named_event)

    def execute_before(self, sensor_graph, scope_stack):
        """Execute statement before children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]

        if self.explicit_stream is None:
            stream = parent.resolve_identifier(self.named_event, DataStream)
            trigger = TrueTrigger()
        else:
            stream = self.explicit_stream
            trigger = self.explicit_trigger

        new_scope = TriggerScope(sensor_graph, scope_stack, (stream, trigger))
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
