"""Standalone TileBus definition compiler.

This script allows you compile .bus files into a
variety of output formats.
"""

from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
import sys
import argparse
from iotile.core.exceptions import ArgumentError, IOTileException
from iotile.build.tilebus import TBDescriptor


DESCRIPTION = \
"""Standalone TileBus definition compiler.

This program takes in one or more TileBus RPC and config variable definition
files (.bus files), merges them together and then compiles them into an
output format.  You can target a json based file for further processing or
a set of embedded C files suitable for inclusion in a TileBus based device.
"""


def build_parser():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-o', '--output', help="The output file to save.  If multiple files are generated this is the output prefix for them all.")
    parser.add_argument('-f', '--format', default="json", choices=['c_files', 'command_map_c', 'command_map_h', 'config_map_c', 'config_map_h', 'json'], type=str, help=u"the output format for the compiled result.")
    parser.add_argument('bus_definition', nargs="+", help="One or more tilebus definition files to compile")

    return parser


def main(raw_args=None):
    """Run the iotile-tbcompile script.

    Args:
        raw_args (list): Optional list of commmand line arguments.  If not
            passed these are pulled from sys.argv.
    """

    multifile_choices = frozenset(['c_files'])

    if raw_args is None:
        raw_args = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(raw_args)

    if args.output is None and args.format in multifile_choices:
        print("You must specify an output file with -o, --output when using a format that produces multiple files (-f %s)" % args.format)
        return 1

    desc = TBDescriptor(args.bus_definition)

    if args.format == 'json':
        print("JSON output is not yet supported")
        return 1

    block = desc.get_block()

    template_map = {
        'command_map_c': 'command_map_c.c.tpl',
        'command_map_h': 'command_map_c.h.tpl',
        'config_map_c': 'config_variables_c.c.tpl',
        'config_map_h': 'config_variables_c.h.tpl'
    }

    template_name = template_map.get(args.format)
    data = block.render_template(template_name)
    print(data)

    return 0
