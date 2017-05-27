"""A SensorGraph simulator that can drive the sensor graph either in realtime or as fast as possible."""

import time
from monotonic import monotonic
from ..known_constants import system_tick, user_tick
from .null_executor import NullRPCExecutor
from .stop_conditions import TimeBasedStopCondition
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.reports import IOTileReading

class SensorGraphSimulator(object):
    """A simulator for sensor graphs.

    At its core the simulator just sends timed inputs to the sensor graph
    every tick and then sits back and lets the nodes process the data in
    whatever way they are configure.

    There are a few things that need to be configured for the simulator to
    function properly however:

    1. There needs to be a stop condition.  When should the simulation
       stop running?  These conditions can either be simulated times like
       one day or other conditions like a certain number of readings.

    2. There needs to be a way to send RPCs.  Most interesting things inside
       of a sensor graph happen because it sent an RPC and processed its response.
       For this to work those RPCs need to be routed somewhere.  By default, all
       RPCs are accepted and a value of 0 is returned, however, you can configure
       the simulator to execute those RPCs on an actual device if you want.

       This results in a semi-hosted sensor graph, where the sensor graph is running
       on your computer but the rpcs are executed on another IOTile Device, which
       can be very useful for exploration and debugging.
    """

    def __init__(self):
        self.stop_conditions = []
        self._known_conditions = []
        self.watch_streams = []
        self.tick_count = 0
        self._rpc_executor = NullRPCExecutor()

        # Register known stop conditions
        self._known_conditions.append(TimeBasedStopCondition)

    def run(self, sensor_graph, include_reset=True, accelerated=True):
        """Run this sensor graph until a stop condition is hit.

        Multiple calls to this function are useful only if
        there has been some change in the stop conditions that would
        cause the second call to not exit immediately.

        Args:
            sensor_graph (SensorGraph): The sensor graph to run
            include_reset (bool): Start the sensor graph run with
                a reset event to match what would happen when an
                actual device powers on.
            accelerated (bool): Whether to run this sensor graph as
                fast as possible or to delay ticke events to simulate
                the actual passage of wall clock time.
        """

        if self._check_stop_conditions(sensor_graph):
            return

        if include_reset:
            pass  # TODO: include a reset event here

        while not self._check_stop_conditions(sensor_graph):
            # Process one more one second tick
            now = monotonic()
            next_tick = now + 1.0

            if (self.tick_count % 10) == 0:
                reading = IOTileReading(system_tick.encode(), self.tick_count, self.tick_count)
                sensor_graph.process_input(system_tick, reading, self._rpc_executor)

            self.tick_count += 1
            now = monotonic()

            # If we are trying to execute this sensor graph in realtime, wait for
            # the remaining slice of this tick.
            if (not accelerated) and (now < next_tick):
                time.sleep(next_tick - now)

    def _check_stop_conditions(self, sensor_graph):
        """Check if any of our stop conditions are met.

        Args:
            sensor_graph (SensorGraph): The sensor graph we are currently simulating

        Returns:
            bool: True if we should stop the simulation
        """

        for stop in self.stop_conditions:
            if stop.should_stop(self.tick_count, sensor_graph):
                return True

        return False

    def stop_condition(self, condition):
        """Add a stop condition to this simulation.

        Stop conditions are specified as strings and parsed into
        the appropriate internal structures.

        Args:
            condition (str): a string description of the stop condition
        """

        # Try to parse this into a stop condition with each of our registered
        # condition types
        for cond_format in self._known_conditions:
            try:
                cond = cond_format.FromString(condition)
                self.stop_conditions.append(cond)
                return
            except ArgumentError:
                continue

        raise ArgumentError("Stop condition could not be processed by any known StopCondition type", condition=condition, suggestion="It may be mistyped or otherwise invalid.")
