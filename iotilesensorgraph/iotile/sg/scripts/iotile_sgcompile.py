"""Command line script to compile a sensor graph."""

import sys
import argparse
from builtins import str
from iotile.sg import SensorGraph, SensorLog, DeviceModel
from iotile.sg.parser import SensorGraphFileParser


def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=u'Compile a sensor graph.')
    parser.add_argument(u'sensor_graph', type=str, help=u"the sensor graph file to load and run.")
    parser.add_argument(u'-f', u'--format', default=u"nodes", choices=[u'nodes', u'ast'], type=str, help=u"the output format for the compiled result.")
    parser.add_argument(u'-o', u'--output', type=str, help=u"the output file to save the results (defaults to stdout)")

    return parser


def main():
    arg_parser = build_args()
    args = arg_parser.parse_args()

    model = DeviceModel()

    parser = SensorGraphFileParser()
    parser.parse_file(args.sensor_graph)

    outfile = sys.stdout

    if args.output is not None:
        outfile = open(args.output, "wb")

    if args.format == u'ast':
        outfile.write(parser.dump_tree())
        outfile.close()
        sys.exit(0)

    parser.compile(model)

    if args.format == u'nodes':
        for node in parser.sensor_graph.dump_nodes():
            outfile.write(node + u'\n')

    outfile.close()
