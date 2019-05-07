"""A websocket client that replicates the state of the supervisor."""

import threading
from copy import copy
import logging
import asyncio
import inspect

from iotile.core.hw.exceptions import RPCInvalidArgumentsError, RPCInvalidReturnValueError
from iotile.core.utilities import SharedLoop
from iotile.core.exceptions import ArgumentError
from iotile_transport_websocket import AsyncValidatingWSClient
from .protocol import OPERATIONS, MESSAGES
from . import states


class AsyncSupervisorClient(AsyncValidatingWSClient):
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

    def __init__(self, url, dispatcher=None, agent=None, logger_name=__name__, loop=SharedLoop):
        super(AsyncSupervisorClient, self).__init__(url, loop=loop)

        # This is a multithreading lock so that we can use local_* methods
        # outside of the background loop and ensure that the underlying
        # data will not change while we copy it.
        self._state_lock = threading.Lock()

        self._rpc_dispatcher = dispatcher

        self._loop = loop
        self._logger = logging.getLogger(logger_name)
        self._on_change_callback = None
        self._agent = agent
        self._name_map = {}

        self.services = {}

        # Register callbacks for all of the status notifications
        self.register_event(OPERATIONS.EVENT_STATUS_CHANGED, self._on_status_change,
                            MESSAGES.ServiceStatusEvent)
        self.register_event(OPERATIONS.EVENT_SERVICE_ADDED, self._on_service_added,
                            MESSAGES.ServiceAddedEvent)
        self.register_event(OPERATIONS.EVENT_HEARTBEAT_RECEIVED, self._on_heartbeat,
                            MESSAGES.HeartbeatReceivedEvent)
        self.register_event(OPERATIONS.EVENT_NEW_MESSAGE, self._on_message,
                            MESSAGES.NewMessageEvent)
        self.register_event(OPERATIONS.EVENT_NEW_HEADLINE, self._on_headline,
                            MESSAGES.NewHeadlineEvent)
        self.register_event(OPERATIONS.EVENT_RPC_COMMAND, self._on_rpc_command,
                            MESSAGES.RPCCommandEvent)
        self.allow_exception(ArgumentError)

    async def start(self):
        await super(AsyncSupervisorClient, self).start(name="supervisor_client")

        await self._populate_name_map()

        if self._agent is not None:
            await self.register_agent(self._agent)
            self._logger.info("Registered as rpc agent for service %s", self._agent)

    async def _populate_name_map(self):
        """Populate the name map of services as reported by the supervisor"""

        services = await self.sync_services()

        with self._state_lock:
            self.services = services

            for i, name in enumerate(self.services.keys()):
                self._name_map[i] = name

    def notify_changes(self, callback):
        """Register to receive a callback when a service changes state.

        Args:
            callback (callable): A function to be called with signature
                callback(short_name, id, state, is_new, new_headline)
        """

        self._on_change_callback = callback

    def local_service(self, name_or_id):
        """Get the locally synced information for a service.

        This method is safe to call outside of the background event loop
        without any race condition.  Internally it uses a thread-safe mutex to
        protect the local copies of supervisor data and ensure that it cannot
        change while this method is iterating over it.

        Args:
            name_or_id (string or int): Either a short name for the service or
                a numeric id.

        Returns:
            ServiceState: the current state of the service synced locally
                at the time of the call.
        """

        if not self._loop.inside_loop():
            self._state_lock.acquire()

        try:
            if isinstance(name_or_id, int):
                if name_or_id not in self._name_map:
                    raise ArgumentError("Unknown ID used to look up service", id=name_or_id)
                name = self._name_map[name_or_id]
            else:
                name = name_or_id
            if name not in self.services:
                raise ArgumentError("Unknown service name", name=name)

            return copy(self.services[name])
        finally:
            if not self._loop.inside_loop():
                self._state_lock.release()

    def local_services(self):
        """Get a list of id, name pairs for all of the known synced services.

        This method is safe to call outside of the background event loop
        without any race condition.  Internally it uses a thread-safe mutex to
        protect the local copies of supervisor data and ensure that it cannot
        change while this method is iterating over it.

        Returns:
            list (id, name): A list of tuples with id and service name sorted by id
                from low to high
        """

        if not self._loop.inside_loop():
            self._state_lock.acquire()

        try:
            return sorted([(index, name) for index, name in self._name_map.items()], key=lambda element: element[0])
        finally:
            if not self._loop.inside_loop():
                self._state_lock.release()

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

        resp = await self.send_command(OPERATIONS.CMD_QUERY_MESSAGES, {'name': name},
                                       MESSAGES.QueryMessagesResponse, timeout=5.0)

        return [states.ServiceMessage.FromDictionary(x) for x in resp]

    async def get_headline(self, name):
        """Get stored messages for a service.

        Args:
            name (string): The name of the service to get messages from.

        Returns:
            ServiceMessage: the headline or None if no headline has been set
        """

        resp = await self.send_command(OPERATIONS.CMD_QUERY_HEADLINE, {'name': name},
                                       MESSAGES.QueryHeadlineResponse, timeout=5.0)

        if resp is not None:
            resp = states.ServiceMessage.FromDictionary(resp)

        return resp

    async def list_services(self):
        """Get the current list of services from the server.

        Returns:
            list(string): A list of the short service names known
                to the supervisor
        """

        return await self.send_command(OPERATIONS.CMD_LIST_SERVICES, None,
                                       MESSAGES.ServiceListResponse, timeout=5.0)

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

        return await self.send_command(OPERATIONS.CMD_QUERY_INFO, {'name': name},
                                       MESSAGES.QueryInfoResponse, timeout=5.0)

    async def send_heartbeat(self, name):
        """Send a heartbeat for a service.

        Args:
            name (string): The name of the service to send a heartbeat for
        """

        await self.send_command(OPERATIONS.CMD_HEARTBEAT, {'name': name},
                                MESSAGES.HeartbeatResponse, timeout=5.0)

    async def update_state(self, name, state):
        """Update the state for a service.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """

        await self.send_command(OPERATIONS.CMD_UPDATE_STATE,
                                {'name': name, 'new_status': state},
                                MESSAGES.UpdateStateResponse, timeout=5.0)

    def post_headline(self, name, level, message):
        """Asynchronously update the sticky headline for a service.

        Args:
            name (string): The name of the service
            level (int): A message level in states.*_LEVEL
            message (string): The user facing error message that will be stored
                for the service and can be queried later.
        """

        self.post_command(OPERATIONS.CMD_SET_HEADLINE,
                          {'name': name, 'level': level, 'message': message})

    def post_state(self, name, state):
        """Asynchronously try to update the state for a service.

        If the update fails, nothing is reported because we don't wait for a
        response from the server.  This function will return immmediately and
        not block.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """

        self.post_command(OPERATIONS.CMD_UPDATE_STATE,
                          {'name': name, 'new_status': state})

    def post_error(self, name, message):
        """Asynchronously post a user facing error message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing error message that will be stored
                for the service and can be queried later.
        """

        self.post_command(OPERATIONS.CMD_POST_MESSAGE,
                          _create_message(name, states.ERROR_LEVEL, message))

    def post_warning(self, name, message):
        """Asynchronously post a user facing warning message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing warning message that will be stored
                for the service and can be queried later.
        """

        self.post_command(OPERATIONS.CMD_POST_MESSAGE,
                          _create_message(name, states.WARNING_LEVEL, message))

    def post_info(self, name, message):
        """Asynchronously post a user facing info message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing info message that will be stored
                for the service and can be queried later.
        """
        self.post_command(OPERATIONS.CMD_POST_MESSAGE,
                          _create_message(name, states.INFO_LEVEL, message))

    async def service_status(self, name):
        """Pull the current status of a service by name.

        Returns:
            dict: A dictionary of service status
        """

        return await self.send_command(OPERATIONS.CMD_QUERY_STATUS, {'name': name},
                                       MESSAGES.QueryStatusResponse, timeout=5.0)

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

        msg = dict(name=name, rpc_id=rpc_id, payload=payload, timeout=timeout)

        try:
            resp = await self.send_command(OPERATIONS.CMD_SEND_RPC, msg,
                                           MESSAGES.SendRPCResponse, timeout=timeout + 1)
        except asyncio.TimeoutError:
            resp = dict(result='timeout', response=b'')

        return resp

    async def register_service(self, short_name, long_name, allow_duplicate=True):
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

        try:
            await self.send_command(OPERATIONS.CMD_REGISTER_SERVICE, dict(name=short_name, long_name=long_name),
                                    MESSAGES.RegisterServiceResponse)
        except ArgumentError:
            if not allow_duplicate:
                raise

    async def register_agent(self, short_name):
        """Register to act as the RPC agent for this service.

        After this call succeeds, all requests to send RPCs to this service
        will be routed through this agent.

        Args:
            short_name (str): A unique short name for this service that functions
                as an id
        """

        await self.send_command(OPERATIONS.CMD_SET_AGENT, {'name': short_name},
                                MESSAGES.SetAgentResponse)

    async def _on_status_change(self, update):
        """Update a service that has its status updated."""

        info = update['payload']
        new_number = info['new_status']
        name = update['service']

        if name not in self.services:
            return

        with self._state_lock:
            is_changed = self.services[name].state != new_number
            self.services[name].state = new_number

        # Notify about this service state change if anyone is listening
        if self._on_change_callback and is_changed:
            self._on_change_callback(name, self.services[name].id, new_number, False, False)

    async def _on_service_added(self, update):
        """Add a new service."""

        info = update['payload']
        name = info['short_name']

        if name in self.services:
            return

        with self._state_lock:
            new_id = len(self.services)
            serv = states.ServiceState(name, info['long_name'],
                                       info['preregistered'], new_id)
            self.services[name] = serv
            self._name_map[new_id] = name

        # Notify about this new service if anyone is listening
        if self._on_change_callback:
            self._on_change_callback(name, new_id, serv.state, True, False)

    async def _on_heartbeat(self, update):
        """Receive a new heartbeat for a service."""

        name = update['service']

        if name not in self.services:
            return

        with self._state_lock:
            self.services[name].heartbeat()

    async def _on_message(self, update):
        """Receive a message from a service."""

        name = update['service']
        message_obj = update['payload']

        if name not in self.services:
            return

        with self._state_lock:
            self.services[name].post_message(message_obj['level'], message_obj['message'])

    async def _on_headline(self, update):
        """Receive a headline from a service."""

        name = update['service']
        message_obj = update['payload']
        new_headline = False

        if name not in self.services:
            return

        with self._state_lock:
            self.services[name].set_headline(message_obj['level'], message_obj['message'])

            if self.services[name].headline.count == 1:
                new_headline = True

        # Notify about this service state change if anyone is listening
        # headline changes are only reported if they are not duplicates
        if self._on_change_callback and new_headline:
            self._on_change_callback(name, self.services[name].id, self.services[name].state, False, True)

    async def _on_rpc_command(self, event):
        """Received an RPC command that we should execute."""

        payload = event['payload']
        rpc_id = payload['rpc_id']
        tag = payload['response_uuid']
        args = payload['payload']

        result = 'success'
        response = b''

        if self._rpc_dispatcher is None or not self._rpc_dispatcher.has_rpc(rpc_id):
            result = 'rpc_not_found'
        else:
            try:
                response = self._rpc_dispatcher.call_rpc(rpc_id, args)
                if inspect.isawaitable(response):
                    response = await response
            except RPCInvalidArgumentsError:
                result = 'invalid_arguments'
                response = b''
            except RPCInvalidReturnValueError:
                result = 'invalid_response'
                response = b''
            except Exception: #pylint:disable=broad-except;We are being called in a background task
                self._logger.exception("Exception handling RPC 0x%04X", rpc_id)
                result = 'execution_exception'
                response = b''

        message = dict(response_uuid=tag, result=result, response=response)
        try:
            await self.send_command(OPERATIONS.CMD_RESPOND_RPC, message,
                                    MESSAGES.RespondRPCResponse)
        except:  #pylint:disable=bare-except;We are being called in a background worker
            self._logger.exception("Error sending response to RPC 0x%04X", rpc_id)


class SupervisorClient:
    """A websocket client that syncs the state of all known services.

    On creation it connects to the supervisor service and gets the
    current status of each known service.  Then it listens for
    change notifications and updates it internal map of service states.

    Each service is assigned a unique number based on the order in
    which it was registered.

    Other clients can dispatch RPCs to this service if it registers
    as an RPC agent, and they are handled by forwarding them on to
    callbacks on the passed dispatcher object which should be a subclass
    of RPCDispatcher.

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

    def __init__(self, url, dispatcher=None, agent=None, logger_name=__name__, loop=SharedLoop):
        self._client = AsyncSupervisorClient(url, dispatcher, agent, loop=loop)
        self._loop = loop
        self._logger = logging.getLogger(logger_name)
        self._loop.run_coroutine(self._client.start())
        self.services = self._client.services

    def notify_changes(self, callback):
        """Register to receive a callback when a service changes state.

        Args:
            callback (callable): A function to be called with signature
                callback(short_name, id, state, is_new, new_headline)
        """

        self._client.notify_changes(callback)

    def local_service(self, name_or_id):
        """Get the locally synced information for a service.

        Args:
            name_or_id (string or int): Either a short name for the service or
                a numeric id.

        Returns:
            ServiceState: the current state of the service synced locally
                at the time of the call.
        """

        return self._client.local_service(name_or_id)

    def local_services(self):
        """Get a list of id, name pairs for all of the known synced services.

        Returns:
            list (id, name): A list of tuples with id and service name sorted by id
                from low to high
        """

        return self._client.local_services()

    def sync_services(self):
        """Poll the current state of all services.

        Returns:
            dict: A dictionary mapping service name to service status
        """

        return self._loop.run_coroutine(self._client.sync_services())

    def get_messages(self, name):
        """Get stored messages for a service.

        Args:
            name (string): The name of the service to get messages from.

        Returns:
            list(ServiceMessage): A list of the messages stored for this service
        """

        return self._loop.run_coroutine(self._client.get_messages(name))

    def get_headline(self, name):
        """Get stored messages for a service.

        Args:
            name (string): The name of the service to get messages from.

        Returns:
            ServiceMessage: the headline or None if no headline has been set
        """

        return self._loop.run_coroutine(self._client.get_headline(name))

    def list_services(self):
        """Get the current list of services from the server.

        Returns:
            list(string): A list of the short service names known
                to the supervisor
        """

        return self._loop.run_coroutine(self._client.list_services())

    def send_heartbeat(self, name):
        """Send a heartbeat for a service.

        Args:
            name (string): The name of the service to send a heartbeat for
        """

        return self._loop.run_coroutine(self._client.send_heartbeat(name))

    def service_info(self, name):
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

        return self._loop.run_coroutine(self._client.service_info(name))

    def update_state(self, name, state):
        """Update the state for a service.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """

        self._loop.run_coroutine(self._client.update_state(name, state))

    def post_headline(self, name, level, message):
        """Asynchronously update the sticky headline for a service.

        Args:
            name (string): The name of the service
            level (int): A message level in states.*_LEVEL
            message (string): The user facing error message that will be stored
                for the service and can be queried later.
        """

        self._client.post_headline(name, level, message)

    def post_state(self, name, state):
        """Asynchronously try to update the state for a service.

        If the update fails, nothing is reported because we don't wait for a
        response from the server.  This function will return immmediately and not block.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """

        self._client.post_state(name, state)

    def post_error(self, name, message):
        """Asynchronously post a user facing error message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing error message that will be stored
                for the service and can be queried later.
        """

        self._client.post_error(name, message)

    def post_warning(self, name, message):
        """Asynchronously post a user facing warning message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing warning message that will be stored
                for the service and can be queried later.
        """

        self._client.post_warning(name, message)

    def post_info(self, name, message):
        """Asynchronously post a user facing info message about a service.

        Args:
            name (string): The name of the service
            message (string): The user facing info message that will be stored
                for the service and can be queried later.
        """

        self._client.post_info(name, message)

    def service_status(self, name):
        """Pull the current status of a service by name.

        Returns:
            dict: A dictionary of service status
        """

        return self._loop.run_coroutine(self._client.service_status(name))

    def send_rpc(self, name, rpc_id, payload, timeout=1.0):
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

        return self._loop.run_coroutine(self._client.send_rpc(name, rpc_id, payload, timeout))

    def register_service(self, short_name, long_name, allow_duplicate=True):
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

        self._loop.run_coroutine(self._client.register_service(short_name, long_name, allow_duplicate))

    def register_agent(self, short_name):
        """Register to act as the RPC agent for this service.

        After this cal succeeds, all requests to send RPCs to this service will be routed
        through this agent.

        Args:
            short_name (str): A unique short name for this service that functions
                as an id
        """

        self._loop.run_coroutine(self._client.register_agent(short_name))

    def stop(self):
        """Disconnect from the supervisor and stop all activity.

        This method should only be called once in an instance's
        lifecycle.
        """

        self._loop.run_coroutine(self._client.stop())


def _create_message(name, level, message):
    return {'name': name, 'level': level, 'message': message}
