"""A command line script to print the contents of an UpdateScript."""

from __future__ import unicode_literals, absolute_import, print_function
import sys
import argparse
import logging
from iotile.core.hw import UpdateScript
from iotile.core.exceptions import ArgumentError, DataError

DESCRIPTION = \
"""Print information about an IOTile update script.

This program takes in a binary UpdateScript object, parses it and prints out
information about it.  It is able to decode the script into the series of high
level operations that it contains including decoding multi-step operations
back into their high level logical equivalent such as 'Program SensorGraph'
rather than a series of 'Add Node' and 'Add Streamer' actions.
"""

def build_args():
    """Create command line parser."""

    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('script', type=str, help="The binary update script to load")
    parser.add_argument('-v', '--verbose', action="count", help="Increase logging level (goes error, warn, info, debug)")
    parser.add_argument('--allow-unknown', '-u', action="store_true", help="Don't complain if the script contains unknown actions")
    parser.add_argument('-f', '--format', choices=['text', 'json'], default="text", help="The output format to use to display the script")

    return parser


def main(argv=None):
    """Main script entry point.

    Args:
        argv (list): The command line arguments, defaults to sys.argv if not passed.

    Returns:
        int: The return value of the script.
    """

    if argv is None:
        argv = sys.argv[1:]

    parser = build_args()
    args = parser.parse_args(args=argv)
    verbosity = args.verbose

    root = logging.getLogger()

    formatter = logging.Formatter('%(levelname).6s %(name)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    loglevels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    if verbosity >= len(loglevels):
        verbosity = len(loglevels) - 1

        level = loglevels[verbosity]
        root.setLevel(level)
        root.addHandler(handler)
    else:
        root.addHandler(logging.NullHandler())

    try:
        with open(args.script, "rb") as infile:
            binary_script = infile.read()
    except IOError as exc:
        print("ERROR: Unable to read script file: %s" % str(exc))
        return 1

    try:
        script = UpdateScript.FromBinary(binary_script, allow_unknown=args.allow_unknown)
    except ArgumentError as err:
        print("ERROR: could not parse script")
        print(str(err))
        return 3
    except DataError as err:
        print("ERROR: could not parse script")
        print(str(err))
        return 4

    if args.format != 'text':
        print("ERROR: only text format is currently supported")
        return 2

    if args.format == 'text':
        print("\nUpdate Script")
        print("-------------")
        print("Path: %s" % args.script)
        print("Record Count: %d" % len(script.records))
        print("Total length: %d bytes" % len(binary_script))

        print("\nActions")
        print("-------")

        for i, record in enumerate(script.records):
            print("%02d: %s" % (i + 1, str(record)))

        print("")

    return 0
