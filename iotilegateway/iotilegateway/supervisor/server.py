"""Websocket server for iotile supervisor."""
import uuid
import logging
import functools
import asyncio
from iotile.core.utilities import SharedLoop
from iotile_transport_websocket import AsyncValidatingWSServer
from .service_manager import ServiceManager
from .protocol import MESSAGES, OPERATIONS


class IOTileSupervisor:
    """A log and rpc broker for daemon tasks.

    This class runs a websocket server that allows tasks to connect to it
    using :class:`SupervisorClient` and :class:`AsyncSupervisorClient`. The
    classes can be used to post log messages and status information about the
    task to the supervisor, which is automatically distributed and synced to
    all other clients so the latest information about all tasks is locally
    known to all tasks.

    You can also register to receive RPCs in your task which other tasks can
    call.  This supervisor server acts as the broker that forwards RPCs from
    one task to another.

    Args:
        config (dict): A dictionary of configuration options.
            Currently supported options are 'port' and 'host',
            which default to 9400 and '127.0.0.1'.  If you pass
            None for 'port' a random port will be used and available
            on self.port after ``start`` has returned.
        loop (BackgroundEventLoop): The background event loop that
            should be used to run the server.  Defaults to the global
            shared loop.
    """

    def __init__(self, config, *, loop=SharedLoop):

        expected_services = config.get('expected_services', [])

        self.port = config.get('port', 9400)
        self.host = config.get('host', '127.0.0.1')

        self.service_manager = ServiceManager(expected_services, loop=loop)

        self.server = AsyncValidatingWSServer(self.host, self.port, loop=loop)
        self.server.prepare_conn = self.prepare_conn
        self.server.teardown_conn = self.teardown_conn

        self.server.register_command(OPERATIONS.CMD_LIST_SERVICES, self.list_services,
                                     MESSAGES.ServiceListCommand)
        self.server.register_command(OPERATIONS.CMD_QUERY_STATUS, self.service_status,
                                     MESSAGES.QueryStatusCommand)
        self.server.register_command(OPERATIONS.CMD_QUERY_MESSAGES, self.service_messages,
                                     MESSAGES.QueryMessagesCommand)
        self.server.register_command(OPERATIONS.CMD_QUERY_HEADLINE, self.service_headline,
                                     MESSAGES.QueryHeadlineCommand)
        self.server.register_command(OPERATIONS.CMD_QUERY_INFO, self.service_info,
                                     MESSAGES.QueryInfoCommand)

        # Commands for updating information about a service
        self.server.register_command(OPERATIONS.CMD_SET_HEADLINE, self.set_headline,
                                     MESSAGES.SetHeadlineCommand)
        self.server.register_command(OPERATIONS.CMD_POST_MESSAGE, self.post_message,
                                     MESSAGES.PostMessageCommand)
        self.server.register_command(OPERATIONS.CMD_UPDATE_STATE, self.update_state,
                                     MESSAGES.UpdateStateCommand)
        self.server.register_command(OPERATIONS.CMD_HEARTBEAT, self.post_heartbeat,
                                     MESSAGES.HeartbeatCommand)

        # Commands for registering services/agents
        self.server.register_command(OPERATIONS.CMD_REGISTER_SERVICE, self.register_service,
                                     MESSAGES.RegisterServiceCommand)
        self.server.register_command(OPERATIONS.CMD_SET_AGENT, self.set_agent,
                                     MESSAGES.SetAgentCommand)

        # Commands for sending and responding to RPCs
        self.server.register_command(OPERATIONS.CMD_SEND_RPC, self.send_rpc,
                                     MESSAGES.SendRPCCommand)
        self.server.register_command(OPERATIONS.CMD_RESPOND_RPC, self.respond_rpc,
                                     MESSAGES.RespondRPCCommand)

        self.clients = {}
        self._logger = logging.getLogger(__name__)

    async def start(self):
        """Start the supervisor server."""

        await self.server.start()
        self.port = self.server.port

    async def stop(self):
        """Stop the supervisor server."""

        await self.server.stop()

    async def prepare_conn(self, conn):
        """Setup a new connection from a client."""

        client_id = str(uuid.uuid4())
        monitor = functools.partial(self.send_event, client_id)

        self._logger.info("New client connection: %s", client_id)

        self.service_manager.add_monitor(monitor)

        self.clients[client_id] = dict(connection=conn, monitor=monitor)
        return client_id

    async def teardown_conn(self, context):
        """Teardown a connection from a client."""

        client_id = context.user_data

        self._logger.info("Tearing down client connection: %s", client_id)
        if client_id not in self.clients:
            self._logger.warning("client_id %s did not exist in teardown_conn", client_id)
        else:
            del self.clients[client_id]

    async def send_event(self, client_id, service_name, event_name, event_info, directed_client=None):
        """Send an event to a client."""

        if directed_client is not None and directed_client != client_id:
            return

        client_info = self.clients.get(client_id)
        if client_info is None:
            self._logger.warning("Attempted to send event to invalid client id: %s", client_id)
            return

        conn = client_info['connection']

        event = dict(service=service_name)
        if event_info is not None:
            event['payload'] = event_info

        self._logger.debug("Sending event: %s", event)

        await self.server.send_event(conn, event_name, event)

    async def send_rpc(self, msg, _context):
        """Send an RPC to a service on behalf of a client."""

        service = msg.get('name')
        rpc_id = msg.get('rpc_id')
        payload = msg.get('payload')
        timeout = msg.get('timeout')

        response_id = await self.service_manager.send_rpc_command(service, rpc_id, payload,
                                                                  timeout)

        try:
            result = await self.service_manager.rpc_results.get(response_id, timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("RPC 0x%04X on service %s timed out after %f seconds",
                                 rpc_id, service, timeout)
            result = dict(result='timeout', response=b'')

        return result

    async def respond_rpc(self, msg, _context):
        """Respond to an RPC previously sent to a service."""

        rpc_id = msg.get('response_uuid')
        result = msg.get('result')
        payload = msg.get('response')

        self.service_manager.send_rpc_response(rpc_id, result, payload)

    async def register_service(self, msg, _context):
        """Register a new service."""

        await self.service_manager.add_service(**msg)

    async def set_agent(self, msg, context):
        """Mark a client as the RPC agent for a service."""

        service = msg.get('name')
        client = context.user_data

        self.service_manager.set_agent(service, client)

    async def post_message(self, msg, _context):
        """Post a message on behalf of a service."""

        await self.service_manager.send_message(**msg)

    async def set_headline(self, msg, _context):
        """Set the headline for a service."""

        await self.service_manager.set_headline(**msg)

    async def post_heartbeat(self, msg, _context):
        """Update the status of a service."""

        name = msg.get('name')

        await self.service_manager.send_heartbeat(name)

    async def update_state(self, msg, _context):
        """Update the status of a service."""

        name = msg.get('name')
        status = msg.get('new_status')

        await self.service_manager.update_state(name, status)

    async def list_services(self, _msg, _context):
        """List the shortname of all known services."""

        return self.service_manager.list_services()

    async def service_info(self, msg, _context):
        """Get info for a given service."""

        return self.service_manager.service_info(msg.get('name'))

    async def service_messages(self, msg, _context):
        """Get all messages for a service."""

        msgs = self.service_manager.service_messages(msg.get('name'))
        return [x.to_dict() for x in msgs]

    async def service_headline(self, msg, _context):
        """Get the headline for a service."""

        headline = self.service_manager.service_headline(msg.get('name'))
        if headline is not None:
            headline = headline.to_dict()

        return headline

    async def service_status(self, msg, _context):
        """Get the status for a service."""

        return self.service_manager.service_status(msg.get('name'))
