"""Class for managing logs and state from various services."""

from monotonic import monotonic
from collections import namedtuple
import uuid
from iotile.core.exceptions import ArgumentError
import states

InFlightRPC = namedtuple('InFlightRPC', ['sender', 'service', 'sent_timestamp', 'timeout'])


class ServiceManager(object):
    """A simple repository for handling the state of a running service and querying log messages from it.

    Args:
        expected_services (list): A list of dictionaries with the name of expected services that should be running
            other services may register on the fly but expected services will allow reporting of a
            NOT_STARTED status and querying the number of services that should be running.
    """

    def __init__(self, expected_services):
        self.services = {}
        self.agents = {}
        self.in_flight_rpcs = {}
        self._monitors = set()

        for service in expected_services:
            self.add_service(service['short_name'], service['long_name'], preregistered=True)

    def add_monitor(self, callback):
        """Register a callback whenever a service changes.

        Args:
            callback (callable): A callback with signature callback(short_name, update)
                where update is a dictionary with the keys:
                    type: one of state_change, heartbeat, new_log, new_message, new_service
                    info: optional dictionary that depends on the type of the message
        """

        self._monitors.add(callback)

    def remove_monitor(self, callback):
        """Remove a previously registered callback.

        Args:
            callback (callable): A callback that was previously registered
        """

        try:
            self._monitors.remove(callback)
        except KeyError:
            raise ArgumentError("Callback was not registered")

    def _notify_update(self, name, change_type, change_info=None, directed_client=None):
        """Notify updates on a service to anyone who cares."""

        for monitor in self._monitors:
            try:
                monitor(name, change_type, change_info, directed_client=directed_client)
            except Exception:
                # We can't allow any exceptions in a monitor routine to break the server.
                pass

    def update_state(self, short_name, state):
        """Set the current state of a service.

        If the state is unchanged from a previous attempt, this routine does
        nothing.

        Args:
            short_name (string): The short name of the service
            state (int): The new stae of the service
        """

        if short_name not in self.services:
            raise ArgumentError("Service name is unknown", short_name=short_name)

        if state not in states.KNOWN_STATES:
            raise ArgumentError("Invalid service state", state=state)

        serv = self.services[short_name]['state']

        if serv.state == state:
            return

        update = {}
        update['old_status'] = serv.state
        update['new_status'] = state
        update['new_status_string'] = states.KNOWN_STATES[state]

        serv.state = state
        self._notify_update(short_name, 'state_change', update)

    def add_service(self, short_name, long_name, preregistered=False):
        """Add a service to the list of tracked services.

        Args:
            short_name (string): A unique short service name for the service
            long_name (string): A longer, user friendly name for the service
            preregistered (bool): Whether this service is an expected preregistered
                service.
        """

        if short_name in self.services:
            raise ArgumentError("Could not add service because the short_name is taken", short_name=short_name)

        serv_state = states.ServiceState(short_name, long_name, preregistered)

        service = {
            'state': serv_state,
            'heartbeat_threshold': 600
        }

        self.services[short_name] = service
        self._notify_update(short_name, 'new_service', self.service_info(short_name))

    def service_info(self, short_name):
        """Get static information about a service.

        Args:
            short_name (string): The short name of the service to query

        Returns:
            dict: A dictionary with the long_name and preregistered info
                on this service.
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        info = {}
        info['short_name'] = short_name
        info['long_name'] = self.services[short_name]['state'].long_name
        info['preregistered'] = self.services[short_name]['state'].preregistered

        return info

    def service_messages(self, short_name):
        """Get the messages stored for a service.

        Args:
            short_name (string): The short name of the service to get messages for

        Returns:
            list(ServiceMessage): A list of the ServiceMessages stored for this service
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        return self.services[short_name]['state'].messages

    def service_headline(self, short_name):
        """Get the headline stored for a service.

        Args:
            short_name (string): The short name of the service to get messages for

        Returns:
            ServiceMessage: the headline or None if there is no headline
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        return self.services[short_name]['state'].headline

    def service_status(self, short_name):
        """Get the current status of a service.

        Returns information about the service such as the length since the last
        heartbeat, any status messages that have been posted about the service
        and whether the heartbeat should be considered out of the ordinary.

        Args:
            short_name (string): The short name of the service to query

        Returns:
            dict: A dictionary with the status of the service
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        info = {}

        service = self.services[short_name]['state']

        info['heartbeat_age'] = monotonic() - service.last_heartbeat
        info['numeric_status'] = service.state
        info['string_status'] = service.string_state

        return info

    def send_message(self, short_name, level, message):
        """Post a message for a service.

        Args:
            short_name (string): The short name of the service to query
            level (int): The level of the message (info, warning, error)
            message (string): The message contents
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        now = monotonic()

        self.services[short_name]['state'].post_message(level, message)
        self._notify_update(short_name, 'new_message', {'level': level, 'message': message, 'created_time': now, 'now_time': now})

    def set_headline(self, short_name, level, message):
        """Set the sticky headline for a service.

        Args:
            short_name (string): The short name of the service to query
            level (int): The level of the message (info, warning, error)
            message (string): The message contents
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        now = monotonic()

        self.services[short_name]['state'].set_headline(level, message)
        self._notify_update(short_name, 'new_headline', {'level': level, 'message': message, 'created_time': now, 'now_time': now})

    def send_heartbeat(self, short_name):
        """Post a heartbeat for a service.

        Args:
            short_name (string): The short name of the service to query
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        self.services[short_name]['state'].heartbeat()
        self._notify_update(short_name, 'heartbeat')

    def list_services(self):
        """Get a list of the services known to this ServiceManager.

        Returns:
            list(string): A list of string short names for the known services
        """

        return self.services.keys()

    def set_agent(self, short_name, client_id):
        """Register a client id that handlers commands for a service.

        Args:
            short_name (str): The name of the service to set an agent
                for.
            client_id (str): A globally unique id for the client that
                should receive commands for this service.
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        self.agents[short_name] = client_id

    def clear_agent(self, short_name, client_id):
        """Remove a client id from being the command handler for a service.

        Args:
            short_name (str): The name of the service to set an agent
                for.
            client_id (str): A globally unique id for the client that
                should no longer receive commands for this service.
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        if short_name not in self.agents:
            raise ArgumentError("No agent registered for service", short_name=short_name)

        if client_id != self.agents[short_name]:
            raise ArgumentError("Client was not registered for service", short_name=short_name, client_id=client_id, current_client=self.agents[short_name])

        del self.agents[short_name]

    def send_rpc_command(self, short_name, rpc_id, payload, sender_client, timeout=1.0):
        """Send an RPC to a service using its registered agent.

        Args:
            short_name (str): The name of the service we would like to send
                and RPC to
            rpc_id (int): The rpc id that we would like to call
            payload (bytes): The raw bytes that we would like to send as an
                argument
            sender_client (str): The uuid of the sending client
            timeout (float): The maximum number of seconds before we signal a timeout
                of the RPC

        Returns:
            str: A unique id that can used to identify the notified response of this
                RPC.
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        if short_name not in self.agents:
            raise ArgumentError("No agent registered for service", short_name=short_name)

        agent_tag = self.agents[short_name]
        rpc_tag = str(uuid.uuid4())

        rpc_message = {
            'rpc_id': rpc_id,
            'payload': payload,
            'response_uuid': rpc_tag
        }

        self.in_flight_rpcs[rpc_tag] = InFlightRPC(sender_client, short_name, monotonic(), timeout)
        self._notify_update(short_name, 'rpc_command', rpc_message, directed_client=agent_tag)

        return rpc_tag

    def send_rpc_response(self, rpc_tag, result, response):
        """Send a response to an RPC.

        Args:
            rpc_tag (str): The exact string given in a previous call to send_rpc_command
            result (str): The result of the operation.  The possible values of response are:
                service_not_found, rpc_not_found, timeout, success, invalid_response,
                invalid_arguments, execution_exception
            response (bytes): The raw bytes that we should send back as a response.
        """

        if rpc_tag not in self.in_flight_rpcs:
            raise ArgumentError("In flight RPC could not be found, it may have timed out", rpc_tag=rpc_tag)

        rpc = self.in_flight_rpcs[rpc_tag]
        del self.in_flight_rpcs[rpc_tag]

        response_message = {
            'payload': response,
            'result': result,
            'response_uuid': rpc_tag
        }

        self._notify_update(rpc.service, 'rpc_response', response_message, directed_client=rpc.sender)

    def periodic_service_rpcs(self):
        """Check if any RPC has expired and remove it from the in flight list.

        This function should be called periodically to expire any RPCs that never complete.
        """

        to_remove = []

        now = monotonic()
        for rpc_tag, rpc in self.in_flight_rpcs.iteritems():
            expiry = rpc.sent_timestamp + rpc.timeout
            if now > expiry:
                to_remove.append(rpc_tag)

        for tag in to_remove:
            del self.in_flight_rpcs[tag]
