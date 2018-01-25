"""Command line script to load and run a sensor graph."""

import sys
import argparse
from builtins import str
from iotile.core.exceptions import ArgumentError, IOTileException
from iotile.sg import DeviceModel, DataStreamSelector, SlotIdentifier
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg.sim.hosted_executor import SemihostedRPCExecutor
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.known_constants import user_connected
from iotile.sg.optimizer import SensorGraphOptimizer

DESCRIPTION = \
u"""Load and run a sensor graph, either in a simulator or on a physical device.

This program takes in a sensor graph description file and simulates it.  The
simulation can run without any physical device present, e.g. entirely on your
computer.  However, if you want you can also simulate the sensor graph in a
semihosted fashion, which means that the graph is still being evaluated on
your computer, but any RPCs it sends will be forwarded on to an actual device
for execution.

semihosting mode:
To activate semihosting mode you need to specify a -p option and a -d option.
The -p option is the port to use to connect to a device, and has the same format
as the --port argument given to the "iotile hw" command. The -d option is the
device id (also knows at the UUID of the device) and is an integer which can be
specified either decimal or hex (with a 0x prefix). See the examples section for
more details.

injecting stimuli:
Sometimes you need to be able to provide specific inputs to a sensor graph at
certain times in order to explore different potential execution paths.  Consider
for example, a sensor graph that only recorded data received on input 1. You
need to provide input 1 to your graph in order for it to do anything.  Use the
-i option to define stimuli.  You can specify as many as you want by using
multiple -i options.  The format for each is:

[number time_unit: ][system ]input X = Y
This specifies that the value Y on input X will be presented to the sensor graph
at the specified time.  If the time is omitted, it is set to the value 0 and
given at the start of the simulation.  Each stimulus is only applied once.  An
example of a valid stimulus is "1 minute: input 5 = 1", which means present the
value 1 on stream 'input 5' after 1 simulated minute (60 ticks).

examples:
    iotile-sgrun -p bled112 -d 25 <sensor_graph file>
        This will simulate the given sensor graph file on device id 25 that is
        connected via bluetooth using a bled112 bluetooth adapter.  There is
        no stop condition so the simulation will run until the user cancels it
        with a ctrl-c combination.

    iotile-sgrun -i "input 1 = 5" <sensor_graph file> -s "run_time 1 minute"
        This will run the simulation for exactly 60 simulated seconds and begin
        the simulation by injecting the value 5 onto input 1 exactly once.
"""


def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(u'sensor_graph', type=str, help=u"The sensor graph file to load and run.")
    parser.add_argument(u'--stop', u'-s', action=u"append", default=[], type=str, help=u"A stop condition for when the simulation should end.")
    parser.add_argument(u'--realtime', u'-r', action=u"store_true", help=u"Do not accelerate the simulation, pin the ticks to wall clock time")
    parser.add_argument(u'--watch', u'-w', action=u"append", default=[], help=u"A stream to watch and print whenever writes are made.")
    parser.add_argument(u'--trace', u'-t', help=u"Trace all writes to output streams to a file")
    parser.add_argument(u'--disable-optimizer', action="store_true", help=u"disable the sensor graph optimizer completely")
    parser.add_argument(u"--mock-rpc", u"-m", action=u"append", type=str, default=[], help=u"mock an rpc, format should be <slot id>:<rpc_id> = value.  For example -m \"slot 1:0x500a = 10\"")
    parser.add_argument(u"--port", u"-p", help=u"The port to use to connect to a device if we are semihosting")
    parser.add_argument(u"--semihost-device", u"-d", type=lambda x: int(x, 0), help=u"The device id of the device we should semihost this sensor graph on.")
    parser.add_argument(u"-c", u"--connected", action="store_true", help=u"Simulate with a user connected to the device (to enable realtime outputs)")
    parser.add_argument(u"-i", u"--stimulus", action=u"append", default=[], help="Push a value to an input stream at the specified time (or before starting).  The syntax is [time: ][system ]input X = Y where X and Y are integers")
    return parser


def process_mock_rpc(input_string):
    """Process a mock RPC argument.

    Args:
        input_string (str): The input string that should be in the format
            <slot id>:<rpc id> = value
    """

    spec, equals, value = input_string.partition(u'=')

    if len(equals) == 0:
        print("Could not parse mock RPC argument: {}".format(input_string))
        sys.exit(1)

    try:
        value = int(value.strip(), 0)
    except ValueError as exc:
        print("Could not parse mock RPC value: {}".format(str(exc)))
        sys.exit(1)

    slot, part, rpc_id = spec.partition(u":")
    if len(part) == 0:
        print("Could not parse mock RPC slot/rpc definition: {}".format(spec))
        sys.exit(1)

    try:
        slot = SlotIdentifier.FromString(slot)
    except ArgumentError as exc:
        print("Could not parse slot id in mock RPC definition: {}".format(exc.msg))
        sys.exit(1)

    try:
        rpc_id = int(rpc_id, 0)
    except ValueError as exc:
        print("Could not parse mock RPC number: {}".format(str(exc)))
        sys.exit(1)

    return slot, rpc_id, value

def watch_printer(watch, value):
    """Print a watched value.

    Args:
        watch (DataStream): The stream that was watched
        value (IOTileReading): The value to was seen
    """

    print("({: 8} s) {}: {}".format(value.raw_time, watch, value.value))


def main(argv=None):
    """Main entry point for iotile sensorgraph simulator.

    This is the iotile-sgrun command line program.  It takes
    an optional set of command line parameters to allow for
    testing.

    Args:
        argv (list of str): An optional set of command line
            parameters.  If not passed, these are taken from
            sys.argv.
    """

    if argv is None:
        argv = sys.argv[1:]

    try:
        executor = None
        parser = build_args()
        args = parser.parse_args(args=argv)

        model = DeviceModel()

        parser = SensorGraphFileParser()
        parser.parse_file(args.sensor_graph)
        parser.compile(model)

        if not args.disable_optimizer:
            opt = SensorGraphOptimizer()
            opt.optimize(parser.sensor_graph, model=model)

        graph = parser.sensor_graph
        sim = SensorGraphSimulator(graph)

        for stop in args.stop:
            sim.stop_condition(stop)

        for watch in args.watch:
            watch_sel = DataStreamSelector.FromString(watch)
            graph.sensor_log.watch(watch_sel, watch_printer)

        # If we are semihosting, create the appropriate executor connected to the device
        if args.semihost_device is not None:
            executor = SemihostedRPCExecutor(args.port, args.semihost_device)
            sim.rpc_executor = executor

        for mock in args.mock_rpc:
            slot, rpc_id, value = process_mock_rpc(mock)
            sim.rpc_executor.mock(slot, rpc_id, value)

        for stim in args.stimulus:
            sim.stimulus(stim)

        graph.load_constants()

        if args.trace is not None:
            sim.record_trace()

        try:
            if args.connected:
                sim.step(user_connected, 8)

            sim.run(accelerated=not args.realtime)
        except KeyboardInterrupt:
            pass

        if args.trace is not None:
            sim.trace.save(args.trace)
    finally:
        if executor is not None:
            executor.hw.close()

    return 0
