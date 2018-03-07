"""A SensorGraph simulator that can drive the sensor graph either in realtime or as fast as possible."""

import time
from monotonic import monotonic
from ..known_constants import system_tick, fast_tick, tick_1, tick_2, battery_voltage
from .null_executor import NullRPCExecutor
from .stop_conditions import TimeBasedStopCondition
from .trace import SimulationTrace
from .stimulus import SimulationStimulus
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

    Args:
        sensor_graph (SensorGraph): The sensor graph that we want to simulate.
    """

    def __init__(self, sensor_graph):
        self.voltage = 3.6
        self.stop_conditions = []
        self.stimuli = []
        self._known_conditions = []
        self.trace = None
        self.tick_count = 0
        self.sensor_graph = sensor_graph
        self._start_tick = 0  # the tick on which the current simulation started
        self.rpc_executor = NullRPCExecutor()

        # Register known stop conditions
        self._known_conditions.append(TimeBasedStopCondition)

    def record_trace(self, selectors=None):
        """Record a trace of readings produced by this simulator.

        This causes the property `self.trace` to be populated with a
        SimulationTrace object that contains all of the readings that
        are produced during the course of the simulation.  Only readings
        that respond to specific selectors are given.

        You can pass whatever selectors you want in the optional selectors
        argument.  If you pass None, then the default behavior to trace
        all of the output streams of the sensor graph, which are defined
        as the streams that are selected by a DataStreamer object in the
        sensor graph.  This is typically what is meant by sensor graph
        output.

        You can inspect the current trace by looking at the trace
        property.  It will initially be an empty list and will be updated
        with each call to step() or run() that results in new readings
        responsive to the selectors you pick (or the graph streamers if
        you did not explicitly pass a list of DataStreamSelector objects).

        Args:
            selectors (list of DataStreamSelector): The selectors to add watch
                statements on to produce this trace. This is optional.
                If it is not specified, a the streamers of the sensor
                graph are used.
        """

        if selectors is None:
            selectors = [x.selector for x in self.sensor_graph.streamers]

        self.trace = SimulationTrace(selectors=selectors)

        for sel in selectors:
            self.sensor_graph.sensor_log.watch(sel, self._on_trace_callback)

    def _on_trace_callback(self, watch, value):
        self.trace.append(value)

    def step(self, input_stream, value):
        """Step the sensor graph through one since input.

        The internal tick count is not advanced so this function may
        be called as many times as desired to input specific conditions
        without simulation time passing.

        Args:
            input_stream (DataStream): The input stream to push the
                value into
            value (int): The reading value to push as an integer
        """

        reading = IOTileReading(input_stream.encode(), self.tick_count, value)
        self.sensor_graph.process_input(input_stream, reading, self.rpc_executor)

    def run(self, include_reset=True, accelerated=True):
        """Run this sensor graph until a stop condition is hit.

        Multiple calls to this function are useful only if
        there has been some change in the stop conditions that would
        cause the second call to not exit immediately.

        Args:
            include_reset (bool): Start the sensor graph run with
                a reset event to match what would happen when an
                actual device powers on.
            accelerated (bool): Whether to run this sensor graph as
                fast as possible or to delay tick events to simulate
                the actual passage of wall clock time.
        """

        self._start_tick = self.tick_count

        if self._check_stop_conditions(self.sensor_graph):
            return

        if include_reset:
            pass  # TODO: include a reset event here

        # Process all stimuli that occur at the start of the simulation
        i = None
        for i, stim in enumerate(self.stimuli):
            if stim.time != 0:
                break

            reading = IOTileReading(self.tick_count, stim.stream.encode(), stim.value)
            self.sensor_graph.process_input(stim.stream, reading, self.rpc_executor)

        if i is not None and i > 0:
            self.stimuli = self.stimuli[i:]

        while not self._check_stop_conditions(self.sensor_graph):
            # Process one more one second tick
            now = monotonic()
            next_tick = now + 1.0

            # To match what is done in actual hardware, we increment tick count so the first tick
            # is 1.
            self.tick_count += 1

            # Process all stimuli that occur at this tick of the simulation
            i = None
            for i, stim in enumerate(self.stimuli):
                if stim.time != self.tick_count:
                    break

                reading = IOTileReading(self.tick_count, stim.stream.encode(), stim.value)
                self.sensor_graph.process_input(stim.stream, reading, self.rpc_executor)

            if i is not None and i > 0:
                self.stimuli = self.stimuli[i:]

            self._check_additional_ticks(self.tick_count)

            if (self.tick_count % 10) == 0:
                reading = IOTileReading(self.tick_count, system_tick.encode(), self.tick_count)
                self.sensor_graph.process_input(system_tick, reading, self.rpc_executor)

                # Every 10 seconds the battery voltage is reported in 16.16 fixed point format in volts
                reading = IOTileReading(self.tick_count, battery_voltage.encode(), int(self.voltage * 65536))
                self.sensor_graph.process_input(battery_voltage, reading, self.rpc_executor)

            now = monotonic()

            # If we are trying to execute this sensor graph in realtime, wait for
            # the remaining slice of this tick.
            if (not accelerated) and (now < next_tick):
                time.sleep(next_tick - now)

    def _check_additional_ticks(self, tick_value):
        fast_interval = self.sensor_graph.get_tick('fast')
        tick_1_interval = self.sensor_graph.get_tick('user1')
        tick_2_interval = self.sensor_graph.get_tick('user2')

        if fast_interval != 0 and (tick_value % fast_interval) == 0:
            reading = IOTileReading(self.tick_count, fast_tick.encode(), self.tick_count)
            self.sensor_graph.process_input(fast_tick, reading, self.rpc_executor)

        if tick_1_interval != 0 and (tick_value % tick_1_interval) == 0:
            reading = IOTileReading(self.tick_count, tick_1.encode(), self.tick_count)
            self.sensor_graph.process_input(tick_1, reading, self.rpc_executor)

        if tick_2_interval != 0 and (tick_value % tick_2_interval) == 0:
            reading = IOTileReading(self.tick_count, tick_2.encode(), self.tick_count)
            self.sensor_graph.process_input(tick_2, reading, self.rpc_executor)


    def _check_stop_conditions(self, sensor_graph):
        """Check if any of our stop conditions are met.

        Args:
            sensor_graph (SensorGraph): The sensor graph we are currently simulating

        Returns:
            bool: True if we should stop the simulation
        """

        for stop in self.stop_conditions:
            if stop.should_stop(self.tick_count, self.tick_count - self._start_tick, sensor_graph):
                return True

        return False

    def stimulus(self, stimulus):
        """Add a simulation stimulus at a given time.

        A stimulus is a specific input given to the graph at a specific
        time to a specific input stream.  The format for specifying a
        stimulus is:
        [time: ][system ]input X = Y
        where X and Y are integers.

        This will cause the simulator to inject this input at the given time.
        If you specify a time of 0 seconds, it will happen before the simulation
        starts.  Similarly, if you specify a time of 1 second it will also happen
        before anything else since the simulations start with a tick value of 1.

        The stimulus is injected before any other things happen at each new tick.

        Args:
            stimulus (str or SimulationStimulus): A prebuilt stimulus object or
                a string description of the stimulus of the format:
                [time: ][system ]input X = Y
                where time is optional and defaults to 0 seconds if not specified.

        Examples:
            sim.stimulus('system input 10 = 15')
            sim.stimulus('1 minute: input 1 = 5')
        """

        if not isinstance(stimulus, SimulationStimulus):
            stimulus = SimulationStimulus.FromString(stimulus)

        self.stimuli.append(stimulus)
        self.stimuli.sort(key=lambda x:x.time)

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
