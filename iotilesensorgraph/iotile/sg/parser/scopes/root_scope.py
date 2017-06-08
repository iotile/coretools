from .scope import Scope
from ...stream import DataStream
from ...slot import SlotIdentifier
from ...node import InputTrigger
from ...exceptions import SensorGraphSemanticError
from ...known_constants import system_tick, user_tick, config_user_tick_secs


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
        self.user_tick = None

        self._setup()

    def _setup(self):
        """Prepare for code generation by setting up root clock nodes.

        These nodes are subsequently used as the basis for all clock operations.
        """

        # Create a root system tick and user tick node
        systick = self.allocator.allocate_stream(DataStream.CounterType, attach=True)
        usertick = self.allocator.allocate_stream(DataStream.CounterType, attach=True)

        self.sensor_graph.add_node("({} always) => {} using copy_all_a".format(system_tick, systick))
        self.sensor_graph.add_node("({} always) => {} using copy_all_a".format(user_tick, usertick))
        self.sensor_graph.add_config(SlotIdentifier.FromString('controller'), config_user_tick_secs, 'uint32_t', 1)

        self.system_tick = systick
        self.user_tick = usertick

    def trigger_chain(self):
        """Return a NodeInput tuple for creating a node.

        Returns:
            (StreamIdentifier, InputTrigger)
        """

        raise SensorGraphSemanticError("There is no trigger chain in the root scope since no triggering criteria have been set")

    def clock(self, interval):
        """Return a NodeInput tuple for triggering an event every interval.

        Args:
            interval (int): The interval (in seconds) at which this input should
                trigger.
        """

        if (interval % 10) == 0:
            tick = self.allocator.attach_stream(self.system_tick)
            count = interval // 10
        else:
            tick = self.allocator.attach_stream(self.user_tick)
            count = interval

        trigger = InputTrigger(u'count', '>=', count)
        return (tick, trigger)
