"""Entrypoint for virtual-device script that can serve a Virtual iotile device."""

from __future__ import unicode_literals, print_function, absolute_import
import argparse
import sys
import logging
import json
import imp
import os.path
import inspect
import pkg_resources
from future.utils import itervalues
from iotile.core.hw.virtual import VirtualIOTileDevice, VirtualIOTileInterface


def main(argv=None):
    """Serve access to a virtual IOTile device using a virtual iotile interface."""

    if argv is None:
        argv = sys.argv[1:]

    list_parser = argparse.ArgumentParser(add_help=False)
    list_parser.add_argument('-l', '--list', action='store_true', help="List all known installed interfaces and devices and then exit")

    parser = argparse.ArgumentParser(description="Serve acess to a virtual IOTile device using a virtual IOTile interface")

    parser.add_argument('interface', help="The name of the virtual device interface to use")
    parser.add_argument('device', help="The name of the virtual device to create")
    parser.add_argument('-c', '--config', help="An optional JSON config file with arguments for the interface and device")
    parser.add_argument('-l', '--list', action='store_true', help="List all known installed interfaces and devices and then exit")
    parser.add_argument('-n', '--scenario', help="Load a test scenario from the given file")
    parser.add_argument('-s', '--state', help="Load a given state into the device before starting to serve it.  Only works with emulated devices.")
    parser.add_argument('-d', '--dump', help="Dump the device's state when we exit the program.  Only works with emulated devices.")
    parser.add_argument('-t', '--track', help="Track all changes to the device's state.  Only works with emulated devices.")

    args, _rest = list_parser.parse_known_args(argv)

    if args.list:
        #List out known virtual interfaces
        print("Installed Virtual Interfaces:")
        for entry in pkg_resources.iter_entry_points('iotile.virtual_interface'):
            print('- {}'.format(entry.name))

        print("\nInstalled Virtual Devices:")
        for entry in pkg_resources.iter_entry_points('iotile.virtual_device'):
            print('- {}'.format(entry.name))

        return 0

    args = parser.parse_args(argv)

    config = {}
    iface = None
    if args.config is not None:
        with open(args.config, "r") as conf_file:
            config = json.load(conf_file)

    started = False
    device = None
    stop_immediately = args.interface == 'null'
    try:
        iface = instantiate_interface(args.interface, config)
        device = instantiate_device(args.device, config)

        if args.state is not None:
            print("Loading device state from file %s" % args.state)
            device.load_state(args.state)

        if args.scenario is not None:
            print("Loading scenario from file %s" % args.scenario)

            with open(args.scenario, "r") as infile:
                scenario = json.load(infile)

            # load_metascenario expects a list of scenarios even when there is only one
            if isinstance(scenario, dict):
                scenario = [scenario]

            device.load_metascenario(scenario)

        if args.track is not None:
            print("Tracking all state changes to device")
            device.state_history.enable()

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [AUDIT %(event_name)s] %(message)s'))

        iface.audit_logger.addHandler(handler)
        iface.audit_logger.setLevel(logging.INFO)

        iface.start(device)
        started = True

        print("Starting to serve virtual IOTile device")

        # We need to periodically process events that are queued up in the interface
        while True:
            iface.process()

            if stop_immediately:
                break

    except KeyboardInterrupt:
        print("Break received, cleanly exiting...")
    finally:
        if iface is not None and started:
            iface.stop()

        if args.dump is not None and device is not None:
            print("Dumping final device state to %s" % args.dump)
            device.save_state(args.dump)

        if args.track is not None and device is not None:
            print("Saving state history to file %s" % args.track)
            device.state_history.dump(args.track)

    return 0


def import_device_script(script_path):
    """Import a virtual device from a file rather than an installed module

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

    devs = [x for x in itervalues(mod.__dict__) if inspect.isclass(x) and issubclass(x, VirtualIOTileDevice) and x != VirtualIOTileDevice]
    if len(devs) == 0:
        print("No VirtualIOTileDevice subclasses were defined in script")
        sys.exit(1)
    elif len(devs) > 1:
        print("More than one VirtualIOTileDevice subclass was defined in script: %s" % str(devs))
        sys.exit(1)

    return devs[0]


def instantiate_device(virtual_dev, config):
    """Find a virtual device by name and instantiate it

    Args:
        virtual_dev (string): The name of the pkg_resources entry point corresponding to
            the device.  It should be in group iotile.virtual_device.  If virtual_dev ends
            in .py, it is interpreted as a python script and loaded directly from the script.
        config (dict): A dictionary with a 'device' key with the config info for configuring
            this virtual device.  This is optional.

    Returns:
        VirtualIOTileDevice: The instantiated subclass of VirtualIOTileDevice
    """
    conf = {}
    if 'device' in config:
        conf = config['device']

    #If we're given a path to a script, try to load and use that rather than search for an installed module
    if virtual_dev.endswith('.py'):
        dev = import_device_script(virtual_dev)
        return dev(conf)

    for entry in pkg_resources.iter_entry_points('iotile.virtual_device', name=virtual_dev):
        dev = entry.load()
        return dev(conf)

    print("Could not find an installed virtual device with the given name: {}".format(virtual_dev))
    sys.exit(1)


def instantiate_interface(virtual_iface, config):
    """Find a virtual interface by name and instantiate it

    Args:
        virtual_iface (string): The name of the pkg_resources entry point corresponding to
            the interface.  It should be in group iotile.virtual_interface
        config (dict): A dictionary with a 'interface' key with the config info for configuring
            this virtual interface.  This is optional.

    Returns:
        VirtualInterface: The instantiated subclass of VirtualInterface
    """

    # Allow the null virtual interface for testing
    if virtual_iface == 'null':
        return VirtualIOTileInterface()

    conf = {}
    if 'interface' in config:
        conf = config['interface']

    for entry in pkg_resources.iter_entry_points('iotile.virtual_interface', name=virtual_iface):
        interface = entry.load()
        return interface(conf)

    print("Could not find an installed virtual interface with the given name: {}".format(virtual_iface))
    sys.exit(1)
