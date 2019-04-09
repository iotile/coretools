"""Command line script to load and run a sensor graph."""
import os
import sys
import time
import argparse
import yaml
from iotile.core.exceptions import IOTileException
from iotile.ship.recipe_manager import RecipeManager

DESCRIPTION = \
    u"""Load and run an iotile recipe.
    
    """


def build_args():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('recipe', type=str, help="The recipe file to load and run.")
    parser.add_argument('-d', '--define', action="append", default=[], help="Set a free variable in the recipe")
    parser.add_argument('-l', '--loop', default=None, help="Loop over a free variable")
    parser.add_argument('-i', '--info', action='store_true', help="Lists out all the steps of that recipe, doesn't run the recipe steps")
    parser.add_argument('-a', '--archive', help="Archive the passed yaml recipe and do not run it")
    parser.add_argument('-c', '--config', default=None, help="A YAML config file with variable definitions")

    return parser


def load_variables(defines, config_file):
    """Load all variables from cmdline args and/or a config file.

    Args:
        defines (list of str): A list of name=value pairs that
            define free variables.
        config_file (str): An optional path to a yaml config
            file that defines a single dict with name=value
            variable definitions.
    """

    if config_file is not None:
        with open(config_file, "r") as conf_file:
            variables = yaml.load(conf_file)
    else:
        variables = {}

    for define in defines:
        name, equ, value = define.partition('=')
        if equ != '=':
            print("Invalid variable definition")
            print("- expected name=value")
            print("- found: '%s'" % define)
            sys.exit(1)

        variables[name] = value

    return variables


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

    recipe_name, _ext = os.path.splitext(os.path.basename(args.recipe))

    rm = RecipeManager()
    rm.add_recipe_folder(os.path.dirname(args.recipe), whitelist=[os.path.basename(args.recipe)])
    recipe = rm.get_recipe(recipe_name)

    if args.archive is not None:
        print("Archiving recipe into %s" % args.archive)
        recipe.archive(args.archive)
        return 0

    if args.info:
        print(recipe)
        return 0

    variables = load_variables(args.define, args.config)

    success = 0

    start_time = time.time()

    if args.loop is None:
        try:
            recipe.run(variables)
            success += 1
        except IOTileException as exc:
            print("Error running recipe: %s" % str(exc))
            return 1
    else:
        while True:
            value = input("Enter value for loop variable %s (return to stop): " % args.loop)

            if value == '':
                break

            local_vars = dict(**variables)
            local_vars[args.loop] = value

            try:
                recipe.run(local_vars)
                success += 1
            except IOTileException as exc:
                print("--> ERROR processing loop variable %s: %s" % (value, str(exc)))

    end_time = time.time()
    total_time = end_time - start_time

    if success == 0:
        per_time = 0.0
    else:
        per_time = total_time / success

    print("Performed %d runs in %.1f seconds (%.1f seconds / run)" % (success, total_time, per_time))
    return 0
