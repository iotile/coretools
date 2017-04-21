import signal
import logging
import sys
import tornado.ioloop
import traceback
import json
from tornado.options import define, parse_command_line, options
from supervisor import ServiceStatusClient
import supervisor.states as states
import pkg_resources
import device

from iotile.core.exceptions import ArgumentError, IOTileException


should_close = False
device_manager = None
agents = []

supervisor = None

define('config', help="Config file for defining what adapters and agents to use")


def quit_signal_handler(signum, frame):
    """Signal handler to catch ^C and cleanly shut down."""

    global should_close

    should_close = True
    log = logging.getLogger('tornado.general')
    log.critical('Received stop signal, attempting to stop')


def try_quit():
    """Periodic callback to attempt to cleanly shut down this gateway."""
    global should_close

    if not should_close:
        return

    log = logging.getLogger('tornado.general')

    log.critical("Stopping Gateway Agents")
    for agent in agents:
        try:
            agent.stop()
        except Exception, exc:
            log.error("Error stopping gateway agent: %s", str(exc))
            traceback.print_exc()

    if device_manager is not None:
        log.critical('Stopping Device Adapters')
        try:
            device_manager.stop()
        except Exception, exc:
            log.error("Error stopping device adapters: %s", str(exc))
            traceback.print_exc()

    if supervisor:
        try:
            supervisor.update_state('gateway', states.STOPPED)
            supervisor.post_headline('gateway', states.INFO_LEVEL, 'Stoppped by supervisor')
        except Exception, exc:
            log.error("Error updating service status to stopped: %s", str(exc))
            traceback.print_exc()

        try:
            supervisor.stop()
        except Exception, exc:
            log.error("Error stopping supervisor client: %s", str(exc))
            traceback.print_exc()

    tornado.ioloop.IOLoop.instance().stop()
    log.critical('Stopping event loop and shutting down')


def try_report_status():
    """Periodic callback to report our gateway's status."""

    global supervisor

    if supervisor is None:
        try:
            supervisor = ServiceStatusClient('ws://localhost:9400/services')
            supervisor.register_service('gateway', 'Device Gateway')
            supervisor.post_info('gateway', "Service started successfully")
            supervisor.post_headline('gateway', states.INFO_LEVEL, 'Started successfully')
        except Exception, exc:
            print str(exc)
            return

    supervisor.update_state('gateway', states.RUNNING)
    supervisor.send_heartbeat('gateway')


def find_entry_point(group, name):
    """Find an entry point by name.

    Args:
        group (string): The entry point group like iotile.gateway_agent
        name (string): The name of the entry point to find
    """

    for entry in pkg_resources.iter_entry_points(group, name):
        item = entry.load()
        return item

    raise ArgumentError("Could not find installed plugin by name and group", group=group, name=name)


def main():
    """Main entry point for iotile-gateway."""

    global device_manager, should_close

    log = logging.getLogger('tornado.general')

    parse_command_line()

    config_file = options.config
    if config_file is None:
        print("You must pass a config file using --config=<path to file>")
        sys.exit(1)

    try:
        with open(config_file, "rb") as conf:
            args = json.load(conf)
    except IOError, exc:
        raise ArgumentError("Could not open required config file", path=config_file, error=str(exc))
    except ValueError, exc:
        raise ArgumentError("Could not parse JSON from config file", path=config_file, error=str(exc))
    except TypeError, exc:
        raise ArgumentError("You must pass the path to a json config file", path=config_file)

    if 'agents' not in args:
        args['agents'] = []
        log.warn("No agents defined in arguments to iotile-gateway, this is likely not what you want")
    elif 'adapters' not in args:
        args['adapters'] = []
        log.warn("No device adapters defined in arguments to iotile-gateway, this is likely not what you want")

    loop = tornado.ioloop.IOLoop.instance()

    signal.signal(signal.SIGINT, quit_signal_handler)

    device_manager = device.DeviceManager(loop)

    # Load in all of the gateway agents that are supposed to provide access to
    # the devices in this gateway
    for agent_info in args['agents']:
        if 'name' not in agent_info:
            raise ArgumentError("Invalid agent information in config file", agent_info=agent_info, missing_key='name')

        agent_name = agent_info['name']
        agent_args = agent_info.get('args', {})

        log.info("Loading agent by name '%s'", agent_name)
        agent_class = find_entry_point('iotile.gateway_agent', agent_name)
        try:
            agent = agent_class(agent_args, device_manager, loop)
            agent.start()
            agents.append(agent)
        except IOTileException, exc:
            log.critical("Could not load gateway agent, quitting, error = %s", str(exc))
            should_close = True
            break

    # Load in all of the device adapters that provide access to actual devices
    if not should_close:
        for adapter_info in args['adapters']:
            if 'name' not in adapter_info:
                raise ArgumentError("Invalid adapter information in config file", agent_info=adapter_info, missing_key='name')

            adapter_name = adapter_info['name']
            port_string = adapter_info.get('port', None)

            log.info("Loading device adapter by name '%s' and port '%s'", adapter_name, port_string)
            adapter_class = find_entry_point('iotile.device_adapter', adapter_name)
            adapter = adapter_class(port_string)
            device_manager.add_adapter(adapter)

    # Make sure we have a way to cleanly break out of the event loop on Ctrl-C
    tornado.ioloop.PeriodicCallback(try_quit, 100).start()

    # Try to regularly update a supervisor about our status
    tornado.ioloop.PeriodicCallback(try_report_status, 60000)

    # Try to report status immediately when we start the ioloop
    loop.add_callback(try_report_status)
    loop.start()

    # The loop has been closed, finish and quit
    log.critical("Done stopping loop")
