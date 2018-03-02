from .scope import Scope
from ...stream import DataStream
from ...slot import SlotIdentifier
from ...node import InputTrigger
from ...exceptions import SensorGraphSemanticError
from ...known_constants import (system_tick, fast_tick, config_fast_tick_secs, tick_1,
                                config_tick1_secs, tick_2, config_tick2_secs)


class RootScope(Scope):
    """The global scope that contains all others.

    Args:
        sensor_graph (SensorGraph): The SensorGraph we
            are operating on.
        alloc (StreamAllocator): The global stream allocator we
            are using.
    """

    def __init__(self, sensor_graph, alloc):
        super(RootScope, self).__init__(u"Root Scope", sensor_graph, alloc, None)

        self.system_tick = None
        self.fast_tick = None
        self.user1_tick = None
        self.user2_tick = None

        self._setup()

    def _setup(self):
        """Prepare for code generation by setting up root clock nodes.

        These nodes are subsequently used as the basis for all clock operations.
        """

        # Create a root system ticks and user configurable ticks
        systick = self.allocator.allocate_stream(DataStream.CounterType, attach=True)
        fasttick = self.allocator.allocate_stream(DataStream.CounterType, attach=True)
        user1tick = self.allocator.allocate_stream(DataStream.CounterType, attach=True)
        user2tick = self.allocator.allocate_stream(DataStream.CounterType, attach=True)

        self.sensor_graph.add_node("({} always) => {} using copy_all_a".format(system_tick, systick))
        self.sensor_graph.add_node("({} always) => {} using copy_all_a".format(fast_tick, fasttick))
        self.sensor_graph.add_config(SlotIdentifier.FromString('controller'), config_fast_tick_secs, 'uint32_t', 1)

        self.sensor_graph.add_node("({} always) => {} using copy_all_a".format(tick_1, user1tick))
        self.sensor_graph.add_node("({} always) => {} using copy_all_a".format(tick_2, user2tick))
        self.system_tick = systick
        self.fast_tick = fasttick
        self.user1_tick = user1tick
        self.user2_tick = user2tick

    def trigger_chain(self):
        """Return a NodeInput tuple for creating a node.

        Returns:
            (StreamIdentifier, InputTrigger)
        """

        raise SensorGraphSemanticError("There is no trigger chain in the root scope since no triggering criteria have been set")

    def clock(self, interval, basis="system"):
        """Return a NodeInput tuple for triggering an event every interval.

        Args:
            interval (int): The interval at which this input should
                trigger. If basis == system (the default), this interval must
                be in seconds.  Otherwise it will be in units of whatever the
                basis tick is configured with.
            basis (str): The basis to use for calculating the interval.  This
                can either be system, tick_1 or tick_2.  System means that the
                clock will use either the fast or regular builtin tick.  Passing
                tick_1 or tick_2 will cause the clock to be generated based on
                the selected tick.
        """

        if basis == "system":
            if (interval % 10) == 0:
                tick = self.allocator.attach_stream(self.system_tick)
                count = interval // 10
            else:
                tick = self.allocator.attach_stream(self.fast_tick)
                count = interval

            trigger = InputTrigger(u'count', '>=', count)
            return (tick, trigger)
        elif basis == 'tick_1':
            tick = self.allocator.attach_stream(self.user1_tick)
            trigger = InputTrigger(u'count', '>=', interval)
            return (tick, trigger)
        elif basis == 'tick_2':
            tick = self.allocator.attach_stream(self.user2_tick)
            trigger = InputTrigger(u'count', '>=', interval)
            return (tick, trigger)

        raise SensorGraphSemanticError("Unkwown tick source specified in RootScope.clock", basis=basis)
