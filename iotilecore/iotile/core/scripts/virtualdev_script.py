"""Entrypoint for virtual-device script that can serve a Virtual iotile device."""

import argparse
import sys
import logging
import json
import time
from typedargs.doc_parser import ParsedDocstring
from iotile.core.dev import ComponentRegistry
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.virtual import BaseVirtualDevice
from iotile.core.hw.transport import AbstractDeviceServer, StandardDeviceServer, VirtualDeviceAdapter
from iotile.core.utilities import SharedLoop


def one_line_desc(obj):
    """Get a one line description of a class."""

    logger = logging.getLogger(__name__)

    try:
        doc = ParsedDocstring(obj.__doc__)
        return doc.short_desc
    except:  # pylint:disable=bare-except; We don't want a misbehaving exception to break the program
        logger.warning("Could not parse docstring for %s", obj, exc_info=True)
        return ""


def configure_logging(verbose):
    root = logging.getLogger()

    if verbose > 0:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname).3s %(name)s %(message)s',
                                      '%y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        loglevels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]

        if verbose >= len(loglevels):
            verbose = len(loglevels) - 1

        level = loglevels[verbose]
        root.setLevel(level)
        root.addHandler(handler)
    else:
        root.addHandler(logging.NullHandler())


def main(argv=None, loop=SharedLoop):
    """Serve access to a virtual IOTile device using a virtual iotile interface."""

    if argv is None:
        argv = sys.argv[1:]

    list_parser = argparse.ArgumentParser(add_help=False)
    list_parser.add_argument('-l', '--list', action='store_true', help="List all known installed interfaces and devices and then exit")
    list_parser.add_argument('-v', '--verbose', action="count", default=0, help="Increase logging level (goes error, warn, info, debug)")

    parser = argparse.ArgumentParser(description="Serve acess to a virtual IOTile device using a virtual IOTile interface")

    parser.add_argument('interface', help="The name of the virtual device interface to use")
    parser.add_argument('device', help="The name of the virtual device to create")
    parser.add_argument('-c', '--config', help="An optional JSON config file with arguments for the interface and device")
    parser.add_argument('-l', '--list', action='store_true', help="List all known installed interfaces and devices and then exit")
    parser.add_argument('-n', '--scenario', help="Load a test scenario from the given file")
    parser.add_argument('-s', '--state', help="Load a given state into the device before starting to serve it.  Only works with emulated devices.")
    parser.add_argument('-d', '--dump', help="Dump the device's state when we exit the program.  Only works with emulated devices.")
    parser.add_argument('-t', '--track', help="Track all changes to the device's state.  Only works with emulated devices.")
    parser.add_argument('-v', '--verbose', action="count", default=0, help="Increase logging level (goes error, warn, info, debug)")

    args, _rest = list_parser.parse_known_args(argv)

    if args.list:
        configure_logging(args.verbose)

        reg = ComponentRegistry()
        print("Installed Device Servers:")
        for name, _iface in reg.load_extensions('iotile.device_server', class_filter=AbstractDeviceServer):
            print('- {}'.format(name))

        print("\nInstalled Virtual Devices:")
        for name, dev in reg.load_extensions('iotile.virtual_device', class_filter=BaseVirtualDevice,
                                             product_name="virtual_device"):
            print('- {}: {}'.format(name, one_line_desc(dev)))

        return 0

    args = parser.parse_args(argv)

    configure_logging(args.verbose)

    config = {}
    if args.config is not None:
        with open(args.config, "r") as conf_file:
            config = json.load(conf_file)

    started = False
    device = None
    stop_immediately = args.interface == 'null'
    try:
        server = instantiate_interface(args.interface, config, loop)
        device = instantiate_device(args.device, config, loop)

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

        adapter = VirtualDeviceAdapter(devices=[device], loop=loop)
        server.adapter = adapter

        loop.run_coroutine(adapter.start())

        try:
            loop.run_coroutine(server.start())
        except:
            loop.run_coroutine(adapter.stop())
            adapter = None
            raise

        started = True

        print("Starting to serve virtual IOTile device")

        if stop_immediately:
            return 0

        # We need to periodically process events that are queued up in the interface
        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("Break received, cleanly exiting...")
    finally:
        if args.dump is not None and device is not None:
            print("Dumping final device state to %s" % args.dump)
            device.save_state(args.dump)

        if started:
            loop.run_coroutine(server.stop())
            loop.run_coroutine(adapter.stop())

        if args.track is not None and device is not None:
            print("Saving state history to file %s" % args.track)
            device.state_history.dump(args.track)

    return 0


def instantiate_device(virtual_dev, config, loop):
    """Find a virtual device by name and instantiate it

    Args:
        virtual_dev (string): The name of the pkg_resources entry point corresponding to
            the device.  It should be in group iotile.virtual_device.  If virtual_dev ends
            in .py, it is interpreted as a python script and loaded directly from the script.
        config (dict): A dictionary with a 'device' key with the config info for configuring
            this virtual device.  This is optional.

    Returns:
        BaseVirtualDevice: The instantiated subclass of BaseVirtualDevice
    """
    conf = {}
    if 'device' in config:
        conf = config['device']

    # If we're given a path to a script, try to load and use that rather than search for an installed module
    try:
        reg = ComponentRegistry()

        if virtual_dev.endswith('.py'):
            _name, dev = reg.load_extension(virtual_dev, class_filter=BaseVirtualDevice, unique=True)
        else:
            _name, dev = reg.load_extensions('iotile.virtual_device', name_filter=virtual_dev,
                                             class_filter=BaseVirtualDevice,
                                             product_name="virtual_device", unique=True)

        return dev(conf)
    except ArgumentError as err:
        print("ERROR: Could not load virtual device (%s): %s" % (virtual_dev, err.msg))
        sys.exit(1)


def instantiate_interface(virtual_iface, config, loop):
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
        return StandardDeviceServer(None, {}, loop=loop)

    conf = {}
    if 'interface' in config:
        conf = config['interface']

    try:
        reg = ComponentRegistry()
        if virtual_iface.endswith('.py'):
            _name, iface = reg.load_extension(virtual_iface, class_filter=AbstractDeviceServer, unique=True)
        else:
            _name, iface = reg.load_extensions('iotile.device_server', name_filter=virtual_iface,
                                               class_filter=AbstractDeviceServer, unique=True)

        return iface(None, conf, loop=loop)
    except ArgumentError as err:
        print("ERROR: Could not load device_server (%s): %s" % (virtual_iface, err.msg))
        sys.exit(1)
