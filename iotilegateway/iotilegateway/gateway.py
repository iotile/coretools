"""An IOTile gateway-in-a-box that will connect to devices using device adapters and serve them using agents."""

import logging
from iotile.core.dev import ComponentRegistry
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities import SharedLoop
from .device import AggregatingDeviceAdapter


class IOTileGateway:
    """A gateway that finds IOTile devices using device adapters and serves them using device servers.

    The gateway runs in separate thread inside of a BackgroundEventLoop and
    you can call the synchronous wait function to wait for it to quit.  It
    will loop forever unless you stop it by calling the stop() or
    stop_from_signal() methods.

    IOTileGateway should be thought of as a turn-key gateway object that
    translates requests for IOTile Device access received from one or more
    AbstractDeviceServer into commands sent to one or more
    AbstractDeviceAdapters.  It is a multi-device, multi-user, multi-protocol
    system that can have many connections in flight at the same time, limited
    only by the available resources on the computer that hosts it.

    The arguments dictionary to IOTileGateway class has the same format as the json parameters
    passed to the iotile-gateway script that is just a thin wrapper around this class.

    Args:
        config (dict): The configuration of the gateway.  There should be two keys set:

            servers (list):
                a list of dictionaries with the name of the device server and
                any arguments that should be passed to create it.

            adapters (list):
                a list of dictionaries with the device adapters to add into the gateway
                and any arguments that should be use to create each one.
    """

    def __init__(self, config, loop=SharedLoop):
        self._loop = loop
        self._config = config
        self._logger = logging.getLogger(__name__)

        self.adapters = _load_adapters(self._config.get('adapters', []), self._loop, self._logger)
        self.device_manager = AggregatingDeviceAdapter(adapters=self.adapters, loop=self._loop)
        self.servers = _load_servers(self._config.get('servers', []), self._loop, self._logger, self.device_manager)

    async def start(self):
        """Start the gateway."""

        self._logger.info("Starting all device adapters")
        await self.device_manager.start()

        self._logger.info("Starting all servers")
        for server in self.servers:
            await server.start()

    async def stop(self):
        """Stop the gateway manager and synchronously wait for it to stop."""

        self._logger.info("Stopping all servers")
        for server in self.servers:
            await server.stop()

        self._logger.info("Stopping all device adapters")
        await self.device_manager.stop()


def _load_servers(configs, loop, logger, adapter):
    if len(configs) == 0:
        logger.warning("No servers defined in arguments to iotile-gateway, "
                       "this is likely not what you want")

    reg = ComponentRegistry()
    servers = []

    for agent_info in configs:
        if 'name' not in agent_info:
            logger.error("Invalid server information in gateway config, info=%s, missing_key=%s",
                         str(agent_info), 'name')

            raise ArgumentError("No server name given in config dict: %s" % agent_info)

        agent_name = agent_info['name']
        agent_args = agent_info.get('args', {})

        logger.info("Loading server by name '%s'", agent_name)
        _, agent_class = reg.load_extensions('iotile.device_server', name_filter=agent_name, unique=True)

        try:
            agent = agent_class(adapter, agent_args, loop=loop)
            servers.append(agent)
        except Exception:  # pylint: disable=W0703
            logger.exception("Could not load device server %s, quitting", agent_name)
            raise

    return servers


def _load_adapters(configs, loop, logger):
    if len(configs) == 0:
        logger.warning("No adapters defined in arguments to iotile-gateway, "
                       "this is likely not what you want")

    reg = ComponentRegistry()
    adapters = []

    for adapter_info in configs:
        if 'name' not in adapter_info:
            logger.error("Invalid adapter information in gateway config, info=%s, missing_key=%s",
                         str(adapter_info), 'name')
            raise ArgumentError("No adapter name given in config dict: %s" % adapter_info)

        adapter_name = adapter_info['name']
        port_string = adapter_info.get('port', None)

        logger.info("Loading device adapter by name '%s' and port '%s'", adapter_name, port_string)

        try:
            _, adapter_class = reg.load_extensions('iotile.device_adapter', name_filter=adapter_name, unique=True)
            adapter = adapter_class(port_string, loop=loop)
            adapters.append(adapter)
        except Exception:  # pylint: disable=W0703
            logger.exception("Could not load device adapter %s", adapter_name)
            raise

    return adapters
