import argparse
import pkg_resources
import sys
import logging
import json

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

def instantiate_device(virtual_dev, config):
    """Find a virtual device by name and instantiate it

    Args:
        virtual_dev (string): The name of the pkg_resources entry point corresponding to
            the device.  It should be in group iotile.virtual_device
        config (dict): A dictionary with a 'device' key with the config info for configuring
            this virtual device.  This is optional.

    Returns:
        VirtualIOTileDevice: The instantiated subclass of VirtualIOTileDevice
    """

    conf = {}
    if 'device' in config:
        conf = config['device']

    for entry in pkg_resources.iter_entry_points('iotile.virtual_device', name=virtual_dev):
        dev = entry.load()
        return dev(conf)

    print("Could not find an installed virtual device with the given name: {}".format(virtual_dev))
    sys.exit(1)

def instantiate_interface(virtual_iface, config):
    """Find a virtual interface by name and instantiate it

    Args:
        virtual_iface (string): The name of the pkg_resources entry point corresponding to
            the device.  It should be in group iotile.virtual_device
        config (dict): A dictionary with a 'device' key with the config info for configuring
            this virtual device.  This is optional.

    Returns:
        VirtualInterface: The instantiated subclass of VirtualInterface
    """

    conf = {}
    if 'device' in config:
        conf = config['device']

    for entry in pkg_resources.iter_entry_points('iotile.virtual_interface', name=virtual_iface):
        dev = entry.load()
        return dev(conf)

    print("Could not find an installed virtual interface with the given name: {}".format(virtual_iface))
    sys.exit(1)
