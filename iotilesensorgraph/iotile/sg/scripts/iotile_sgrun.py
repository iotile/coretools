"""Command line script to load and run a sensor graph."""

import sys
import argparse
from builtins import str
from iotile.core.exceptions import ArgumentError
from iotile.sg import DeviceModel, DataStreamSelector, SlotIdentifier
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.optimizer import SensorGraphOptimizer

def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=u'Load and run a sensor graph, either in a simulator or on a physical device.')
    parser.add_argument(u'sensor_graph', type=str, help=u"The sensor graph file to load and run.")
    parser.add_argument(u'--stop', u'-s', action=u"append", type=str, help=u"A stop condition for when the simulation should end.")
    parser.add_argument(u'--realtime', u'-r', action=u"store_true", help=u"A stop condition for when the simulation should end.")
    parser.add_argument(u'--watch', u'-w', action=u"append", help=u"A stream to watch and print whenever writes are made.")
    parser.add_argument(u'--disable-optimizer', action="store_true", help=u"disable the sensor graph optimizer completely")
    parser.add_argument(u"--mock-rpc", "-m", action=u"append", type=str, default=[], help=u"mock an rpc, format should be <slot id>:<rpc_id> = value.  For example -m \"slot 1:0x500a = 10\"")

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

    for mock in args.mock_rpc:
        slot, rpc_id, value = process_mock_rpc(mock)
        sim.rpc_executor.mock(slot, rpc_id, value)

    graph.load_constants()

    try:
        sim.run(graph, accelerated=not args.realtime)
    except KeyboardInterrupt:
        pass
