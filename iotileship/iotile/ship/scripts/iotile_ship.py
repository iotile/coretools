"""Command line script to load and run a sensor graph."""
import os
import sys
import argparse
import yaml
from builtins import str
from iotile.core.exceptions import ArgumentError, IOTileException
from iotile.ship.recipe_manager import RecipeManager

DESCRIPTION = \
u"""Load and run an iotile recipe


"""


def build_args():
    """Create command line argument parser."""
    list_parser = argparse.ArgumentParser(add_help=False)
    list_parser.add_argument('-l', '--list', action='store_true', help="List all known device preparation scripts and then exit")
    
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(u'recipe', type=str, help=u"The recipe file to load and run.")
    parser.add_argument('--uuid', action='append', default=[], help="Run script on device given by this uuid")
    parser.add_argument('--device', action='append', default=[], help="Run script on device given by this connection string")
    parser.add_argument('--pause', action='store_true', help="Pause and wait for user input after finishing each device")
    parser.add_argument('--max-attempts', type=int, default=1, help="Number of times to attempt the operation (up to a max of 5 times)")
    parser.add_argument('--uuid-range', action='append', default=[], help="Process every device in a range (range should be specified as start-end and is inclusive, e.g ab-cd)")
    parser.add_argument('--info', action='store_true', help="Lists out all the steps of that recipe, doesn't run the recipe steps")
    args, rest = list_parser.parse_known_args()
    
    return parser

def main(argv=None):
    """Main entry point for iotile-ship recipe runner.

    This is the iotile-ship command line program. 

    Args:
        argv (list of str): An optional set of command line
            parameters.  If not passed, these are taken from
            sys.argv.
    """

    if argv is None:
        argv = sys.argv[1:]

    parser = build_args()
    args = parser.parse_args(args=argv)

    rm = RecipeManager()
    rm.add_recipe_folder(os.path.dirname(args.recipe))
    recipe = rm.get_recipe(args.recipe)

    if args.info:
        print recipe
        return 0

    devices = []
    success = []
    devices.extend([int(x, 16) for x in args.uuid])
    for uuid_range in args.uuid_range:
        start, _, end = uuid_range.partition('-')
        start = int(start, 16)
        end = int(end, 16)
        devices.extend(xrange(start, end+1))

    try:
        for dev in devices:
            variables = {
                'UUID': dev
            }
            for i in xrange(0, args.max_attempts):
                try:
                    recipe.run(variables)
                except IOTileException, exc:
                    print("--> Error on try %d: %s" % (i+1, str(exc)))
                    continue
            success.append(dev)
            if args.pause:
                raw_input("--> Waiting for <return> before processing next device")
    except KeyboardInterrupt:
        print("Break received, cleanly exiting...")

    print("\n**FINISHED**\n")
    print("Successfully processed %d devices" % len(success))
    for dev in success:
        print("%s" % (dev))

    if len(success) != len(devices):
        return 1
    
    return 0