"""On blocks trigger functions when an event occurs on a stream."""

from builtins import str
from collections import namedtuple
from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from ..scopes import TriggerScope
from ...node import InputTrigger, TrueTrigger
from ... import DataStream
from iotile.core.exceptions import ArgumentError

TriggerDefinition = namedtuple("TriggerDefinition", ['named_event', 'explicit_stream', 'explicit_trigger'])


@python_2_unicode_compatible
class OnBlock(SensorGraphStatement):
    """A block of statements that should run every time an event occurs

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this on block.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, children, location=None):
        trigger_a = parsed[0]

        self.trigger_a = self._parse_trigger(trigger_a)

        if len(parsed) > 1:
            self.combiner = parsed[1]
            self.trigger_b = self._parse_trigger(parsed[2])
        else:
            self.trigger_b = None
            self.combiner = None

        super(OnBlock, self).__init__(children, location)

    def _format_trigger(self, trigger_def):
        if trigger_def.explicit_stream is not None:
            return trigger_def.explicit_trigger.format_trigger(trigger_def.explicit_stream)

        return u"{}".format(trigger_def.named_event)

    def _convert_trigger(self, trigger_def, parent):
        """Convert a TriggerDefinition into a stream, trigger pair."""

        if trigger_def.explicit_stream is None:
            stream = parent.resolve_identifier(trigger_def.named_event, DataStream)
            trigger = TrueTrigger()
        else:
            stream = trigger_def.explicit_stream
            trigger = trigger_def.explicit_trigger

        return (stream, trigger)

    def _parse_trigger(self, trigger_clause):
        """Parse a named event or explicit stream trigger into a TriggerDefinition."""

        cond = trigger_clause[0]

        named_event = None
        explicit_stream = None
        explicit_trigger = None

        # Identifier parse tree is Group(Identifier)
        if cond.getName() == 'identifier':
            named_event = cond[0]
        elif cond.getName() == 'stream_trigger':
            trigger_type = cond[0]
            stream = cond[1]
            oper = cond[2]
            ref = cond[3]

            trigger = InputTrigger(trigger_type, oper, ref)
            explicit_stream = stream
            explicit_trigger = trigger
        elif cond.getName() == 'stream_always':
            stream = cond[0]
            trigger = TrueTrigger()
            explicit_stream = stream
            explicit_trigger = trigger
        else:
            raise ArgumentError("OnBlock created from an invalid ParseResults object", parse_results=trigger_clause)

        return TriggerDefinition(named_event, explicit_stream, explicit_trigger)

    def __str__(self):
        if self.combiner is None:
            return u"on {}".format(self._format_trigger(self.trigger_a))

        return u"on {} {} {}".format(self._format_trigger(self.trigger_a), self.combiner, self._format_trigger(self.trigger_b))

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

        stream_a, trigger_a = self._convert_trigger(self.trigger_a, parent)

        if self.trigger_b is None:
            new_scope = TriggerScope(sensor_graph, scope_stack, (stream_a, trigger_a))
        else:
            stream_b, trigger_b = self._convert_trigger(self.trigger_b, parent)
            trigger_stream = alloc.allocate_stream(DataStream.UnbufferedType)

            if self.combiner == u'and':
                combiner = '&&'
            else:
                combiner = '||'

            sensor_graph.add_node(u"({} {} {} {} {}) => {} using copy_latest_a".format(stream_a, trigger_a, combiner, stream_b, trigger_b, trigger_stream))
            new_scope = TriggerScope(sensor_graph, scope_stack, (trigger_stream, TrueTrigger()))

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
