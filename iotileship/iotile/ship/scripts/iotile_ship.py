"""Command line script to load and run a sensor graph."""
from __future__ import (unicode_literals, absolute_import, print_function)
from builtins import str
import os
import shutil
import sys
import time
import argparse
import yaml
from iotile.core.exceptions import IOTileException
from iotile.ship.recipe_manager import RecipeManager

DESCRIPTION = \
u"""Load and run an iotile recipe


"""


def build_args():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(u'recipe', type=str, help=u"The recipe file to load and run.")
    parser.add_argument('--uuid', action='append', default=[], help="Run script on device given by this uuid")
    parser.add_argument('--device', action='append', default=[], help="Run script on device given by this connection string")
    parser.add_argument('--pause', action='store_true', help="Pause and wait for user input after finishing each device")
    parser.add_argument('--max-attempts', type=int, default=1, help="Number of times to attempt the operation (up to a max of 5 times)")
    parser.add_argument('--uuid-range', action='append', default=[], help="Process every device in a range (range should be specified as start-end and is inclusive, e.g ab-cd)")
    parser.add_argument('-i', '--info', action='store_true', help="Lists out all the steps of that recipe, doesn't run the recipe steps")
    parser.add_argument('--preserve', action='store_true', help="Preserve temporary folder contents after recipe is completed")
    parser.add_argument('-c', '--config', help="An JSON config file with arguments for the script")

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

    #If --info, just print and then end
    if args.info:
        print(recipe)
        return 0

    #Acquiring list of devices
    devices = []
    success = []
    devices.extend([int(x, 16) for x in args.uuid])
    for uuid_range in args.uuid_range:
        start, _, end = uuid_range.partition('-')
        start = int(start, 16)
        end = int(end, 16)
        devices.extend(xrange(start, end+1))

    #Creating temporary directory for intermediate files
    temp_dir = os.path.join(os.path.dirname(args.recipe), 'temp')
    if not os.path.exists(temp_dir):
        os.mkdir(temp_dir)

    #Creating variables from config file
    variables = dict()
    if args.config is not None:
        with open(args.config, "rb") as conf_file:
            variables = yaml.load(conf_file)
    variables['temp_dir'] = temp_dir

    #Attempt to run the recipe on each device
    start_time = time.time()
    try:
        for dev in devices:
            variables['UUID'] = dev
            for i in xrange(0, args.max_attempts):
                try:
                    recipe.run(variables)
                    success.append(dev)
                except IOTileException, exc:
                    print("--> Error on try %d: %s" % (i+1, str(exc)))
                    continue

            if args.pause:
                raw_input("--> Waiting for <return> before processing next device")
    except KeyboardInterrupt:
        print("Break received, cleanly exiting...")

    #Delete tempfile by default, will keep folder if --preserve
    if not args.preserve:
        shutil.rmtree(temp_dir)

    print("\n**FINISHED**\n")
    print("Successfully processed %d devices in %f seconds" % (len(success), time.time()- start_time))

    if len(success) != len(devices):
        return 1
    return 0
