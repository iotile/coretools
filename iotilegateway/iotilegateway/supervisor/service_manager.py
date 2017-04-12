"""Class for managing logs and state from various services
"""

from monotonic import monotonic
from iotile.core.exceptions import ArgumentError

NOT_STARTED = 0
RUNNING = 1
DEGRADED = 2
STOPPED = 3
UNKNOWN = 4

KNOWN_STATES = {
    NOT_STARTED: 'Not Started',
    RUNNING: 'Running',
    STOPPED: 'Stopped',
    UNKNOWN: 'Unknown'
}


class ServiceManager:
    """A simple repository for handling the state of a running service and querying log messages from it

    Args:
        expected_services (dict): A dictionary with the name of expected services that should be running
            other services may register on the fly but expected services will allow reporting of a
            NOT_STARTED status and querying the number of services that should be running.
    """

    def __init__(self, expected_services):
        self.services = {}

        for service in expected_services:
            self.add_service(service['short_name'], service['long_name'])

    def add_service(self, short_name, long_name):
        """Add a service to the list of tracked services

        Args:
            short_name (string): A unique short service name for the service
            long_name (string): A longer, user friendly name for the service
        """

        if short_name in self.services:
            raise ArgumentError("Could not add service because the short_name is taken", short_name=short_name)

        service = {
            'short_name': short_name,
            'long_name': long_name,
            'status': UNKNOWN,
            'last_heartbeat': monotonic(),
            'heartbeat_threshold': 600
        }

        self.services[short_name] = service

    def service_status(self, short_name):
        """Get information about a service

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

        info['heartbeat_bad'] = False

        service = self.services[short_name]

        if service['last_heartbeat'] is not None:
            info['heartbeat_age'] = monotonic() - service['last_heartbeat']

        if info['heartbeat_age'] > service['heartbeat_threshold']:
            info['heartbeat_bad'] = True

        info['numeric_status'] = service['status']
        info['string_status'] = KNOWN_STATES[service['status']]

    def send_heartbeat(self, short_name):
        """Post a heartbeat for a service

        Args:
            short_name (string): The short name of the service to query
        """

        if short_name not in self.services:
            raise ArgumentError("Unknown service name", short_name=short_name)

        self.services[short_name]['last_heartbeat'] = monotonic()

    def list_services(self):
        """Get a list of the services known to this ServiceManager

        Returns:
            list(string): A list of string short names for the known services
        """

        return self.services.keys()
