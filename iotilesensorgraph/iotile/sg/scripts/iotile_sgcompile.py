"""Command line script to compile a sensor graph."""

import sys
import argparse
from io import open
from iotile.sg import DeviceModel
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.optimizer import SensorGraphOptimizer
from iotile.sg.output_formats import KNOWN_FORMATS


def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=u'Compile a sensor graph.')
    parser.add_argument(u'sensor_graph', type=str, help=u"the sensor graph file to load and run.")
    parser.add_argument(u'-f', u'--format', default=u"nodes", choices=[u'nodes', u'ast', u'snippet', u'ascii', u'config', u'script'], type=str, help=u"the output format for the compiled result.")
    parser.add_argument(u'-o', u'--output', type=str, help=u"the output file to save the results (defaults to stdout)")
    parser.add_argument(u'--disable-optimizer', action="store_true", help=u"disable the sensor graph optimizer completely")
    return parser


def write_output(output, text=True, output_path=None):
    """Write binary or text output to a file or stdout."""

    if output_path is None and text is False:
        print("ERROR: You must specify an output file using -o/--output for binary output formats")
        sys.exit(1)

    if output_path is not None:
        if text:
            outfile = open(output_path, "w", encoding="utf-8")
        else:
            outfile = open(output_path, "wb")
    else:
        outfile = sys.stdout

    try:
        if text and isinstance(output, bytes):
            output = output.decode('utf-8')

        outfile.write(output)
    finally:
        if outfile is not sys.stdout:
            outfile.close()


def main():
    """Main entry point for iotile-sgcompile."""

    arg_parser = build_args()
    args = arg_parser.parse_args()

    model = DeviceModel()

    parser = SensorGraphFileParser()
    parser.parse_file(args.sensor_graph)

    if args.format == u'ast':
        write_output(parser.dump_tree(), True, args.output)
        sys.exit(0)

    parser.compile(model)

    if not args.disable_optimizer:
        opt = SensorGraphOptimizer()
        opt.optimize(parser.sensor_graph, model=model)

    if args.format == u'nodes':
        output = u'\n'.join(parser.sensor_graph.dump_nodes()) + u'\n'
        write_output(output, True, args.output)
    else:
        if args.format not in KNOWN_FORMATS:
            print("Unknown output format: {}".format(args.format))
            sys.exit(1)

        output_format = KNOWN_FORMATS[args.format]
        output = output_format.format(parser.sensor_graph)

        write_output(output, output_format.text, args.output)
