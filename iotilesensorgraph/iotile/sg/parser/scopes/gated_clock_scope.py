import logging
from ...node import InputTrigger
from ...stream import DataStream
from ...exceptions import SensorGraphSemanticError
from .scope import Scope


class GatedClockScope(Scope):
    """A scope that will gate all requested clocks with a latch.

    Args:
        sensor_graph (SensorGraph): The sensor graph we are working on.
        scope_stack (list(Scope)): The stack of already allocated scopes.
        input_latch ((DataStream, InputTrigger)): The input stream and condition
            that should be used to gate clocks passed through this scope. The
            stream must already be attached.
    """

    def __init__(self, sensor_graph, scope_stack, input_latch):
        parent = scope_stack[-1]
        alloc = parent.allocator
        sensor_graph = parent.sensor_graph

        super(GatedClockScope, self).__init__(u"Gated Clock Scope", sensor_graph, alloc, parent)

        stream = alloc.allocate_stream(DataStream.ConstantType)
        sensor_graph.add_node(u'({} always) => {} using copy_latest_a'.format(input_latch[0], stream))
        self.latch_stream = stream
        self.latch_trigger = input_latch[1]
        self.clock_cache = {}
        self.logger = logging.getLogger(__name__)

        self.logger.debug("Allocating GatedClockScope on latch stream %s with condition %s", input_latch[0], input_latch[1])

    def _classify_clock(self, interval, basis):
        if basis == 'system':
            if interval % 10 == 0:
                return 'standard'

            return 'fast'
        elif basis == 'tick_1':
            return 'tick_1'
        elif basis == 'tick_2':
            return 'tick_2'

        raise SensorGraphSemanticError("Unknown clock basis in GatedClockScope", scope=self.name, basis=basis, interval=interval)

    def clock(self, interval, basis):
        """Return a NodeInput tuple for triggering an event every interval.

        We request each distinct type of clock at most once and combine it with our
        latch stream each time it is requested.

        Args:
            interval (int): The interval (in seconds) at which this input should
                trigger.
        """

        cache_name = self._classify_clock(interval, basis)
        cache_data = self.clock_cache.get(cache_name)

        if cache_data is None:
            parent_stream, trigger = self.parent.clock(interval, basis)

            if trigger.use_count is False:
                raise SensorGraphSemanticError("Unsupported clock trigger in GatedClockScope", trigger=trigger)
            elif interval % trigger.reference != 0:
                raise SensorGraphSemanticError("Unsupported trigger ratio in GatedClockScope", trigger=trigger, interval=interval)

            ratio = interval // trigger.reference

            stream = self.allocator.allocate_stream(DataStream.CounterType)
            latch_stream = self.allocator.attach_stream(self.latch_stream)

            self.sensor_graph.add_node(u'({} always && {} {}) => {} using copy_latest_a'.format(parent_stream, latch_stream, self.latch_trigger, stream))
            self.clock_cache[cache_name] = (stream, ratio)
        else:
            stream, ratio = cache_data

        if interval % ratio != 0:
            raise SensorGraphSemanticError("Unsupported trigger ratio in GatedClockScope", ratio=ratio, interval=interval)

        count = interval // ratio

        clock_stream = self.allocator.attach_stream(stream)
        return clock_stream, InputTrigger(u'count', '>=', count)
