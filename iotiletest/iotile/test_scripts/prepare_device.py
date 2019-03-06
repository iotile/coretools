import argparse
import pkg_resources
import sys
import json
import os.path
import imp
from iotile.core.exceptions import IOTileException
from iotile.core.hw.hwmanager import HardwareManager


def main():
    """Run a script that puts an IOTile device into a known state"""

    list_parser = argparse.ArgumentParser(add_help=False)
    list_parser.add_argument('-l', '--list', action='store_true', help="List all known device preparation scripts and then exit")

    parser = argparse.ArgumentParser(description="Prepare a device or a list of devices into a known state using a script")

    parser.add_argument('port', help="The name of the port to use to connect to the device")
    parser.add_argument('script', help="The name of the device preparation script to use (can either be an installed script name or a .py file with extension")
    parser.add_argument('-c', '--config', help="An optional JSON config file with arguments for the script")
    parser.add_argument('-l', '--list', action='store_true', help="List all known scripts and then exit")
    parser.add_argument('--uuid', action='append', default=[], help="Run script on device given by this uuid")
    parser.add_argument('--device', action='append', default=[], help="Run script on device given by this connection string")
    parser.add_argument('--pause', action='store_true', help="Pause and wait for user input after finishing each device")
    parser.add_argument('--max-attempts', type=int, default=1, help="Number of times to attempt the operation (up to a max of 5 times)")
    parser.add_argument('--uuid-range', action='append', default=[], help="Process every device in a range (range should be specified as start-end and is inclusive, e.g ab-cd)")
    args, rest = list_parser.parse_known_args()

    if args.list:
        print("\nInstalled Preparation Scripts:")
        for entry in pkg_resources.iter_entry_points('iotile.device_recipe'):
            print('- {}'.format(entry.name))

        return 0

    args = parser.parse_args()

    config = {}
    if args.config is not None:
        with open(args.config, "rb") as conf_file:
            config = json.load(conf_file)

    script = instantiate_script(args.script)

    success = []

    devices = []
    devices.extend([('uuid', int(x, 16)) for x in args.uuid])
    devices.extend([('conection_string', x) for x in args.device])

    for uuid_range in args.uuid_range:
        start, _, end = uuid_range.partition('-')
        start = int(start, 16)
        end = int(end, 16)

        devices.extend([('uuid', x) for x in range(start, end+1)])

    try:
        with HardwareManager(port=args.port) as hw:
            for conntype, dev in devices:
                for i in range(0, args.max_attempts):
                    try:
                        print("Configuring device %s identified by %s" % (str(dev), conntype))
                        configure_device(hw, conntype, dev, script, config)
                        break
                    except IOTileException as exc:
                        print("--> Error on try %d: %s" % (i+1, str(exc)))
                        continue

                success.append((conntype, dev))
                if args.pause:
                    input("--> Waiting for <return> before processing next device")
    except KeyboardInterrupt:
        print("Break received, cleanly exiting...")

    print("\n**FINISHED**\n")
    print("Successfully processed %d devices" % len(success))
    for conntype, conn in success:
        print("%s: %s" % (conntype, conn))

    if len(success) != len(devices):
        return 1

    return 0


def import_device_script(script_path):
    """Import a main function from a script file

    script_path must point to a python file ending in .py that contains exactly one
    VirtualIOTileDevice class definitions.  That class is loaded and executed as if it
    were installed.

    Args:
        script_path (string): The path to the script to load

    Returns:
        VirtualIOTileDevice: A subclass of VirtualIOTileDevice that was loaded from script_path
    """

    search_dir, filename = os.path.split(script_path)
    if search_dir == '':
        search_dir = './'

    if filename == '' or not os.path.exists(script_path):
        print("Could not find script to load virtual device, path was %s" % script_path)
        sys.exit(1)

    module_name, ext = os.path.splitext(filename)
    if ext != '.py':
        print("Script did not end with .py")
        sys.exit(1)

    try:
        file = None
        file, pathname, desc = imp.find_module(module_name, [search_dir])
        mod = imp.load_module(module_name, file, pathname, desc)
    finally:
        if file is not None:
            file.close()

    if not hasattr(mod, 'main'):
        print("Script file had no main function containing a device recipe")
        sys.exit(1)

    return getattr(mod, 'main')


def configure_device(hw, conntype, conarg, script, args):
    if conntype == 'uuid':
        hw.connect(conarg)
    else:
        hw.connect_direct(conarg)

    try:
        script(hw, args)
    finally:
        if hw.stream.connected:
            hw.disconnect()


def instantiate_script(device_recipe):
    """Find a device recipe by name and instantiate it

    Args:
        device_recipe (string): The name of the pkg_resources entry point corresponding to
            the device.  It should be in group iotile.device_recipe

    Returns:
        tuple(callable, dict): A callable function with signature callable(HWManager, config_dict) that
            executes the script and a dictionary that must be kept around as long as callable is.
    """

    if device_recipe.endswith('.py'):
        main_func = import_device_script(device_recipe)
        return main_func

    for entry in pkg_resources.iter_entry_points('iotile.device_recipe', name=device_recipe):
        dev = entry.load()
        return dev

    print("Could not find an installed device preparation script with the given name: {}".format(device_recipe))
    sys.exit(1)
