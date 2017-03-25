import argparse
import pkg_resources
import sys
import logging
import json
import imp
import os.path
import inspect
from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice

def main():
    """Serve access to a virtual IOTile device using a virtual iotile interface
    """

    list_parser = argparse.ArgumentParser(add_help=False)
    list_parser.add_argument('-l', '--list', action='store_true', help="List all known installed interfaces and devices and then exit")

    parser = argparse.ArgumentParser(description="Serve acess to a virtual IOTile device using a virtual IOTile interface")
    
    parser.add_argument('interface', help="The name of the virtual device interface to use")
    parser.add_argument('device', help="The name of the virtual device to create")
    parser.add_argument('-c', '--config', help="An optional JSON config file with arguments for the interface and device")
    parser.add_argument('-l', '--list', action='store_true', help="List all known installed interfaces and devices and then exit")

    args, rest = list_parser.parse_known_args()

    if args.list:
        #List out known virtual interfaces
        print("Installed Virtual Interfaces:")
        for entry in pkg_resources.iter_entry_points('iotile.virtual_interface'):
            print('- {}'.format(entry.name))

        print("\nInstalled Virtual Devices:")
        for entry in pkg_resources.iter_entry_points('iotile.virtual_device'):
            print('- {}'.format(entry.name))

        return 0

    args = parser.parse_args()

    config = {}
    iface = None
    if args.config is not None:
        with open(args.config, "rb") as conf_file:
            config = json.load(conf_file)

    try:
        iface = instantiate_interface(args.interface, config)
        device = instantiate_device(args.device, config)

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [AUDIT %(event_name)s] %(message)s'))

        iface.audit_logger.addHandler(handler)
        iface.audit_logger.setLevel(logging.INFO)

        iface.start(device)

        print("Starting to serve virtual IOTile device")

        #We need to periodically process events that are queued up in the interface
        while True:
            iface.process()

    except KeyboardInterrupt:
        print("Break received, cleanly exiting...")
    finally:
        if iface is not None:
            iface.stop()

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

    devs = filter(lambda x: inspect.isclass(x) and issubclass(x, VirtualIOTileDevice) and x != VirtualIOTileDevice, mod.__dict__.itervalues())
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
        config (dict): A dictionary with a 'device' key with the config info for configuring
            this virtual interface.  This is optional.

    Returns:
        VirtualInterface: The instantiated subclass of VirtualInterface
    """

    conf = {}
    if 'interface' in config:
        conf = config['interface']

    for entry in pkg_resources.iter_entry_points('iotile.virtual_interface', name=virtual_iface):
        dev = entry.load()
        return dev(conf)

    print("Could not find an installed virtual interface with the given name: {}".format(virtual_iface))
    sys.exit(1)
