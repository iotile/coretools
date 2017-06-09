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


def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=u'Load and run a sensor graph, either in a simulator or on a physical device.')
    parser.add_argument(u'sensor_graph', type=str, help=u"The sensor graph file to load and run.")
    parser.add_argument(u'--stop', u'-s', action=u"append", default=[], type=str, help=u"A stop condition for when the simulation should end.")
    parser.add_argument(u'--realtime', u'-r', action=u"store_true", help=u"A stop condition for when the simulation should end.")
    parser.add_argument(u'--watch', u'-w', action=u"append", default=[], help=u"A stream to watch and print whenever writes are made.")
    parser.add_argument(u'--disable-optimizer', action="store_true", help=u"disable the sensor graph optimizer completely")
    parser.add_argument(u"--mock-rpc", u"-m", action=u"append", type=str, default=[], help=u"mock an rpc, format should be <slot id>:<rpc_id> = value.  For example -m \"slot 1:0x500a = 10\"")
    parser.add_argument(u"--port", u"-p", help=u"The port to use to connect to a device if we are semihosting")
    parser.add_argument(u"--semihost-device", u"-d", type=lambda x: int(x, 0), help=u"The device id of the device we should semihost this sensor graph on.")
    parser.add_argument(u"-c", u"--connected", action="store_true", help=u"Simulate with a user connected to the device (to enable realtime outputs)")
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


def main():
    try:
        executor = None
        parser = build_args()
        args = parser.parse_args()

        model = DeviceModel()

        parser = SensorGraphFileParser()
        parser.parse_file(args.sensor_graph)
        parser.compile(model)

        if not args.disable_optimizer:
            opt = SensorGraphOptimizer()
            opt.optimize(parser.sensor_graph, model=model)

        graph = parser.sensor_graph
        sim = SensorGraphSimulator()

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

        graph.load_constants()

        try:
            if args.connected:
                sim.step(graph, user_connected, 8)

            sim.run(graph, accelerated=not args.realtime)
        except KeyboardInterrupt:
            pass
    #except IOTileException as exc:
    #    print(str(exc))
    #    return 1
    finally:
        if executor is not None:
            executor.hw.close()
