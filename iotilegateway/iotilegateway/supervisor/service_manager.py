"""Class for managing logs and state from various services."""

from monotonic import monotonic
from iotile.core.exceptions import ArgumentError
import states


class ServiceManager:
    """A simple repository for handling the state of a running service and querying log messages from it."""

    def __init__(self, expected_services):
        """Constructor.

        Args:
            expected_services (dict): A dictionary with the name of expected services that should be running
                other services may register on the fly but expected services will allow reporting of a
                NOT_STARTED status and querying the number of services that should be running.
        """
        self.services = {}
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

    def _notify_update(self, name, change_type, change_info=None):
        """Notify updates on a service to anyone who cares."""

        for monitor in self._monitors:
            try:
                monitor(name, change_type, change_info)
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
