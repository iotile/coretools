"""An IOTile gateway-in-a-box that will connect to devices using device adapters and serve them using agents."""

import logging
import threading
import pkg_resources
import tornado.ioloop
from iotilegateway.supervisor import ServiceStatusClient
import iotilegateway.supervisor.states as states
import iotilegateway.device as device
from iotile.core.exceptions import ArgumentError


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


class IOTileGateway(threading.Thread):
    """A gateway that finds IOTile devices using device adapters and serves them using agents.

    The gateway runs in separate thread in a tornado IOLoop and you can call the synchronous
    wait function to wait for it to quit.  It will loop forever unless you stop it by calling
    the stop() or stop_from_signal() methods.  These functions add a task to the gateway's
    event loop and implicitly call wait to synchronously wait until the gateway loop actually
    stops.

    IOTileGateway should be thought of as a turn-key gateway object that translates requests
    for IOTile Device access received from one or more GatewayAgents into commands sent to
    one or more DeviceAdapters.  It is a multi-device, multi-user, multi-protocol system that
    can have many connections in flight at the same time, limited only by the available resources
    on the computer that hosts it.

    The arguments dictionary to IOTileGateway class has the same format as the json parameters
    passed to the iotile-gateway script that is just a thin wrapper around this class.

    Args:
        config (dict): The configuration of the gateway.  There should be two keys set:

            agents (list):
                a list of dictionaries with the name of the agent and any arguments that
                should be passed to create it.
            adapters (list):
                a list of dictionaries with the device adapters to add into the gateway
                and any argument sthat should be use to create each one.
    """

    def __init__(self, config):
        self.loop = tornado.ioloop.IOLoop.instance()
        self.device_manager = device.DeviceManager(self.loop)
        self.agents = []
        self.supervisor = None
        self.loaded = threading.Event()

        self._config = config
        self._logger = logging.getLogger(__name__)

        if 'agents' not in config:
            self._config['agents'] = []
            self._logger.warn("No agents defined in arguments to iotile-gateway, this is likely not what you want")
        elif 'adapters' not in config:
            self._config['adapters'] = []
            self._logger.warn("No device adapters defined in arguments to iotile-gateway, this is likely not what you want")

        super(IOTileGateway, self).__init__()

    def run(self):
        """Start the gateway and run it to completion in another thread."""

        # If we have an initialization error, stop trying to initialize more things and
        # just shut down cleanly
        should_close = False

        # Load in all of the gateway agents that are supposed to provide access to
        # the devices in this gateway
        for agent_info in self._config['agents']:
            if 'name' not in agent_info:
                self._logger.error("Invalid agent information in gateway config, info=%s, missing_key=%s", str(agent_info), 'name')
                should_close = True
                break

            agent_name = agent_info['name']
            agent_args = agent_info.get('args', {})

            self._logger.info("Loading agent by name '%s'", agent_name)
            agent_class = find_entry_point('iotile.gateway_agent', agent_name)
            try:
                agent = agent_class(agent_args, self.device_manager, self.loop)
                agent.start()
                self.agents.append(agent)
            except Exception:  # pylint: disable=W0703
                self._logger.exception("Could not load gateway agent %s, quitting", agent_name)
                should_close = True
                break

        # Load in all of the device adapters that provide access to actual devices
        if not should_close:
            for adapter_info in self._config['adapters']:
                if 'name' not in adapter_info:
                    self._logger.error("Invalid adapter information in gateway config, info=%s, missing_key=%s", str(adapter_info), 'name')
                    should_close = True
                    break

                adapter_name = adapter_info['name']
                port_string = adapter_info.get('port', None)

                self._logger.info("Loading device adapter by name '%s' and port '%s'", adapter_name, port_string)

                try:
                    adapter_class = find_entry_point('iotile.device_adapter', adapter_name)
                    adapter = adapter_class(port_string)
                    self.device_manager.add_adapter(adapter)
                except Exception:  # pylint: disable=W0703
                    self._logger.exception("Could not load device adapter %s, quitting", adapter_name)
                    should_close = True

        if should_close:
            self.loop.add_callback(self._stop_loop)
        else:
            # Notify that we have now loaded all plugins and are starting operation
            self.loaded.set()
            # Try to regularly update a supervisor about our status
            callback = tornado.ioloop.PeriodicCallback(self._try_report_status, 60000)
            callback.start()

        self.loop.start()

        # The loop has been closed, finish and quit
        self._logger.critical("Done stopping loop")

    def _try_report_status(self):
        """Periodic callback to report our gateway's status."""

        if self.supervisor is None:
            try:
                self.supervisor = ServiceStatusClient('ws://localhost:9400/services')
                self.supervisor.register_service('gateway', 'Device Gateway')
                self.supervisor.post_info('gateway', "Service started successfully")
                self.supervisor.post_headline('gateway', states.INFO_LEVEL, 'Started successfully')
            except Exception:  # pylint: disable=W0703
                self._logger.exception("Exception trying to create a ServiceStatusClient")
                return

        self.supervisor.update_state('gateway', states.RUNNING)
        self.supervisor.send_heartbeat('gateway')

    def _stop_loop(self):
        """Cleanly stop the gateway and close down the IOLoop.

        This function must be called only by being added to our event loop using add_callback.
        """

        self._logger.critical("Stopping gateway")
        self._logger.info("Stopping gateway agents")

        for agent in self.agents:
            try:
                agent.stop()
            except Exception:  # pylint: disable=W0703
                self._logger.exception("Error stopping gateway agent")

        self._logger.critical('Stopping device adapters')

        try:
            self.device_manager.stop()
        except Exception:  # pylint: disable=W0703
            self._logger.exception("Error stopping device adapters")

        if self.supervisor:
            try:
                self.supervisor.update_state('gateway', states.STOPPED)
                self.supervisor.post_headline('gateway', states.INFO_LEVEL, 'Stoppped by supervisor')
            except Exception:  # pylint: disable=W0703
                self._logger.exception("Error updating service status to stopped")

            try:
                self.supervisor.stop()
            except Exception:  # pylint: disable=W0703
                self._logger.exception("Error stopping IOLoop")

        self.loop.stop()
        self._logger.critical('Stopping event loop and shutting down')

    def stop(self):
        """Stop the gateway manager and synchronously wait for it to stop."""

        self.loop.add_callback(self._stop_loop)
        self.wait()

    def wait(self):
        """Wait for this gateway to shut down.

        We need this special function because waiting inside
        join will cause signals to not get handled.
        """

        while self.is_alive():
            try:
                self.join(timeout=0.1)
            except IOError:
                pass  # IOError comes when this call is interrupted in a signal handler

    def stop_from_signal(self):
        """Stop the gateway from a signal handler, not waiting for it to stop."""

        self.loop.add_callback_from_signal(self._stop_loop)
