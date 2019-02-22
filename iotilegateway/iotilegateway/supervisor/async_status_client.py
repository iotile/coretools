"""A websocket client that replicates the state of the supervisor."""

from copy import copy
from future.utils import viewitems, viewkeys
import logging
from monotonic import monotonic
from iotile.core.hw.virtual import RPCInvalidArgumentsError, RPCInvalidReturnValueError
from iotile.core.utilities.async_validating_wsclient import AsyncValidatingWSClient
from iotile.core.exceptions import ArgumentError
from . import command_formats
from . import states

import asyncio


class AsyncServiceStatusClient(AsyncValidatingWSClient):
    """A async websocket client that syncs the state of all known services.

    On creation it connects to the supervisor service and gets the
    current status of each known service.  Then it listens for
    change notifications and updates it internal map of service states.

    Each service is assigned a unique number based on the order in
    which it was registered.

    Other clients can dispatch RPCs to this service if it registers
    as an RPC agent, and they are handled by forwarding them on to
    callbacks on the passed dispatcher object which should be a subclass
    of RPCQueue.

    You can automatically register as a service agent by passing the
    agent parameters.

    Args:
            url (string): The URL of the websocket server that we want
                to connect to.
            dispatcher (RPCDispatcher): Optional, the object that contains all of the
                RPCs that we implement.
            agent (string): Optional, automatically register as the RPC agent of
                a given service by specifying its short_name
            logger_name (string): An optional name that errors are logged to
    """

    def __init__(self, url, loop, dispatcher=None, agent=None, logger_name=__name__):
        super(AsyncServiceStatusClient, self).__init__(url, loop)

        self._state_lock = asyncio.Lock(loop=loop)
        self._rpc_lock = asyncio.Lock()
        self._rpc_dispatcher = dispatcher
        self._queued_rpcs = []

        self._logger = logging.getLogger(logger_name)
        self.services = {}
        self._name_map = {}
        self._on_change_callback = None

        self.q = asyncio.Queue(loop=loop)

        # Register callbacks for all of the status notifications

        self.add_message_type(command_formats.ServiceStatusChanged, self._on_status_change)
        self.add_message_type(command_formats.ServiceAdded, self._on_service_added)
        self.add_message_type(command_formats.HeartbeatReceived, self._on_heartbeat)
        self.add_message_type(command_formats.NewMessage, self._on_message)
        self.add_message_type(command_formats.NewHeadline, self._on_headline)
        self.add_message_type(command_formats.RPCCommand, self._on_rpc_command)
        self.add_message_type(command_formats.RPCResponse, self._on_rpc_response)

        asyncio.ensure_future(self.populate_name_map(), loop=loop)
        if agent is not None:
            asyncio.ensure_future(self.register_agent(agent), loop=loop)

    async def populate_name_map(self):
        """Populate the name map of services as reported by the supervisor"""

        async with self._state_lock:
            self.services = await self.sync_services()
            for i, name in enumerate(viewkeys(self.services)):
                self._name_map[i] = name

    def notify_changes(self, callback):
        """Register to receive a callback when a service changes state.

        Args:
            callback (callable): A function to be called with signature
                callback(short_name, id, state, is_new, new_headline)
        """

        self._on_change_callback = callback

    async def local_service(self, name_or_id):
        """Get the locally synced information for a service.

        Args:
            name_or_id (string or int): Either a short name for the service or
                a numeric id.

        Returns:
            ServiceState: the current state of the service synced locally
                at the time of the call.
        """

        async with self._state_lock:
            if isinstance(name_or_id, int):
                if name_or_id not in self._name_map:
                    raise ArgumentError("Unknown ID used to look up service", id=name_or_id)
                name = self._name_map[name_or_id]
            else:
                name = name_or_id
            if name not in self.services:
                raise ArgumentError("Unknown service name", name=name)
            service = self.services[name]
            return copy(service)

    async def local_services(self):
        """Get a list of id, name pairs for all of the known synced services.

        Returns:
            list (id, name): A list of tuples with id and service name sorted by id
                from low to high
        """

        async with self._state_lock:
            return sorted([(index, name) for index, name in viewitems(self._name_map)], key=lambda element: element[0])

    async def sync_services(self):
        """Poll the current state of all services.

        Returns:
            dict: A dictionary mapping service name to service status
        """

        services = {}
        servs = await self.list_services()
        for i, serv in enumerate(servs):
            info = await self.service_info(serv)
            status = await self.service_status(serv)
            messages = await self.get_messages(serv)
            headline = await self.get_headline(serv)
            services[serv] = states.ServiceState(info['short_name'], info['long_name'], info['preregistered'], i)
            services[serv].state = status['numeric_status']

            for message in messages:
                services[serv].post_message(message.level, message.message, message.count, message.created)
            if headline is not None:
                services[serv].set_headline(headline.level, headline.message, headline.created)

        return services

    async def get_messages(self, name):
        """Get stored messages for a service.

        Args:
            name (string): The name of the service to get messages from.

        Returns:
            list(ServiceMessage): A list of the messages stored for this service
        """

        resp = await self.send_command('query_messages', {'name': name}, timeout=5.0)
        return [states.ServiceMessage.FromDictionary(x) for x in resp['payload']]

    async def get_headline(self, name):
        """Get stored messages for a service.

        Args:
            name (string): The name of the service to get messages from.

        Returns:
            ServiceMessage: the headline or None if no headline has been set
        """

        resp = await self.send_command('query_headline', {'name': name}, timeout=5.0)
        if 'payload' not in resp:
            return None

        msg = resp['payload']
        return states.ServiceMessage.FromDictionary(msg)

    async def list_services(self):
        """Get the current list of services from the server.

        Returns:
            list(string): A list of the short service names known
                to the supervisor
        """

        resp = await self.send_command('list_services', {}, timeout=5.0)
        return resp['payload']['services']

    async def send_heartbeat(self, name):
        """Send a heartbeat for a service.

        Args:
            name (string): The name of the service to send a heartbeat for
        """

        resp = await self.send_command('heartbeat', {'name': name}, timeout=5.0)
        if resp['success'] is not True:
            raise ArgumentError("Unknown service name", name=name)

    async def service_info(self, name):
        """Pull descriptive info of a service by name.

        Information returned includes the service's user friendly
        name and whether it was preregistered or added dynamically.

        Returns:
            dict: A dictionary of service information with the following keys
                set:
                long_name (string): The user friendly name of the service
                preregistered (bool): Whether the service was explicitly
                    called out as a preregistered service.
        """
        resp = await self.send_command('query_info', {'name': name}, timeout=5.0)
        if resp['success'] is not True:
            raise ArgumentError("Unknown service name", name=name)

        return resp['payload']

    async def update_state(self, name, state):
        """Update the state for a service.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """
        resp = await self.send_command('update_state', {'name': name, 'new_status': state}, timeout=5.0)
        if resp['success'] is not True:
            raise ArgumentError("Error updating service state", reason=resp['reason'])

    async def post_headline(self, name, level, message):
        """Asynchronously update the sticky headline for a service.

        Args:
            name (string): The name of the service
            level (int): A message level in states.*_LEVEL
            message (string): The user facing error message that will be stored
                for the service and can be queried later.
        """

        now = monotonic()
        await self.post_command(
            'set_headline',
            {'name': name, 'level': level, 'message': message, 'created_time': now, 'now_time': now}
        )

    async def post_state(self, name, state):
        """Asynchronously try to update the state for a service.

        If the update fails, nothing is reported because we don't wait for a
        response from the server.  This function will return immmediately and not block.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """

        await self.post_command('update_state', {'name': name, 'new_status': state})

    async def post_error(self, name, message):
        """Asynchronously post a user facing error message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing error message that will be stored
                for the service and can be queried later.
        """

        await self.post_command('post_message', {'name': name, 'level': states.ERROR_LEVEL, 'message': message})

    async def post_warning(self, name, message):
        """Asynchronously post a user facing warning message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing warning message that will be stored
                for the service and can be queried later.
        """

        await self.post_command('post_message', {'name': name, 'level': states.WARNING_LEVEL, 'message': message})

    async def post_info(self, name, message):
        """Asynchronously post a user facing info message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing info message that will be stored
                for the service and can be queried later.
        """

        await self.post_command('post_message', {'name': name, 'level': states.INFO_LEVEL, 'message': message})

    async def service_status(self, name):
        """Pull the current status of a service by name.

        Returns:
            dict: A dictionary of service status
        """

        resp = await self.send_command('query_status', {'name': name}, timeout=5.0)

        if resp['success'] is not True:
            raise ArgumentError("Unknown service name", name=name)

        return resp['payload']

    async def send_rpc(self, name, rpc_id, payload, timeout=1.0):
        """Send an RPC to a service and synchronously wait for the response.

        Args:
            name (str): The short name of the service to send the RPC to
            rpc_id (int): The id of the RPC we want to call
            payload (bytes): Any binary arguments that we want to send
            timeout (float): The number of seconds to wait for the RPC to finish
                before timing out and returning

        Returns:
            dict: A response dictionary with 1 or 2 keys set
                'result': one of 'success', 'service_not_found',
                    or 'rpc_not_found', 'timeout'
                'response': the binary response object if the RPC was successful
        """

        async with self._rpc_lock:
            resp = await self.send_command(
                'send_rpc',
                {'name': name, 'rpc_id': rpc_id, 'payload': payload, 'timeout': timeout}
            )

            result = resp['payload']['result']

            if result == 'service_not_found':
                return {'result': 'service_not_found'}

            try:
                data = await asyncio.wait_for(self.q.get(), timeout=timeout, loop=self.loop)
            except asyncio.TimeoutError:
                return {'result': 'timeout'}

            result = data[0]
            if result != 'success':
                return {'result': result}
            return {'result': 'success', 'response': data[1]}

    async def register_service_async(self, short_name, long_name, allow_duplicate=True):
        """Register a new service with the service manager.

        Args:
            short_name (string): A unique short name for this service that functions
                as an id
            long_name (string): A user facing name for this service
            allow_duplicate (boolean): Don't throw an error if this service is already
                registered.  This is important if the service is preregistered for example.
        Raises:
            ArgumentError: if the short_name is already taken
        """

        async with self._state_lock:
            resp = await self.send_command('register_service', {'name': short_name, 'long_name': long_name})

            if resp['success'] is not True and not allow_duplicate:
                raise ArgumentError("Service name already registered", short_name=short_name)

    async def register_agent(self, short_name):
        """Register to act as the RPC agent for this service.

        After this call succeeds, all requests to send RPCs to this service will be routed
        through this agent.

        Args:
            short_name (str): A unique short name for this service that functions
                as an id
        """

        resp = await self.send_command('set_agent', {'name': short_name})
        if resp['success'] is not True:
            raise ArgumentError("Could not register as agent", short_name=short_name, reason=resp['reason'])

    async def _on_status_change(self, update):
        """Update a service that has its status updated."""

        info = update['payload']
        new_number = info['new_status']
        name = update['name']

        async with self._state_lock:
            if name not in self.services:
                return

            is_changed = self.services[name].state != new_number

            self.services[name].state = new_number

        # Notify about this service state change if anyone is listening
        if self._on_change_callback and is_changed:
            await self._on_change_callback(name, self.services[name].id, new_number, False, False)

    async def _on_service_added(self, update):
        """Add a new service."""

        info = update['payload']
        name = info['short_name']

        async with self._state_lock:
            if name in self.services:
                return

            new_id = len(self.services)
            serv = states.ServiceState(name, info['long_name'], info['preregistered'], new_id)
            self.services[name] = serv
            self._name_map[new_id] = name

        # Notify about this new service if anyone is listening
        if self._on_change_callback:
            self._on_change_callback(name, new_id, serv.state, True, False)

    async def _on_heartbeat(self, update):
        """Receive a new heartbeat for a service."""

        name = update['name']
        async with self._state_lock:
            if name not in self.services:
                return
            self.services[name].heartbeat()

    async def _on_message(self, update):
        """Receive a message from a service."""

        name = update['name']
        message_obj = update['payload']

        async with self._state_lock:
            if name not in self.services:
                return
            self.services[name].post_message(message_obj['level'], message_obj['message'])

    async def _on_headline(self, update):
        """Receive a headline from a service."""

        name = update['name']
        message_obj = update['payload']
        new_headline = False

        async with self._state_lock:
            if name not in self.services:
                return

            self.services[name].set_headline(message_obj['level'], message_obj['message'])

            if self.services[name].headline.count == 1:
                new_headline = True
        # Notify about this service state change if anyone is listening
        # headline changes are only reported if they are not duplicates
        if self._on_change_callback and new_headline:
            self._on_change_callback(name, self.services[name].id, self.services[name].state, False, True)

    async def _on_rpc_response(self, resp):
        """Receive an RPC response for a command that we previously sent."""

        payload = resp['payload']
        data = [payload['result'], payload['payload']]
        await self.q.put(data)

    async def _on_rpc_command(self, cmd):
        """Received an RPC command that we should execute."""

        payload = cmd['payload']
        rpc_id = payload['rpc_id']
        tag = payload['response_uuid']
        args = payload['payload']

        if self._rpc_dispatcher is None or not self._rpc_dispatcher.has_rpc(rpc_id):
            # Fixme: include proper things here
            await self.post_command('rpc_response', {'response_uuid': tag, 'result': 'rpc_not_found', 'response': b''})
            return

        try:
            response = self._rpc_dispatcher.call_rpc(rpc_id, args)
            await self.post_command('rpc_response', {'response_uuid': tag, 'result': 'success', 'response': response})
            return
        except RPCInvalidArgumentsError:
            await self.post_command('rpc_response', {'response_uuid': tag, 'result': 'invalid_arguments', 'response': b''})
        except RPCInvalidReturnValueError:
            await self.post_command('rpc_response', {'response_uuid': tag, 'result': 'invalid_response', 'response': b''})
        except Exception as exc: #pylint:disable=bare-exception
            self.logger.exception("Exception handling RPC 0x%X : %s", rpc_id, str(exc))
            await self.post_command('rpc_response', {'response_uuid': tag, 'result': 'execution_exception', 'response': b''})
