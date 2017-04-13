"""A websocket client that replicates the state of the supervisor."""

from iotile.core.utilities.validating_wsclient import ValidatingWSClient
from iotile.core.exceptions import ArgumentError
from threading import Lock
from copy import copy
import command_formats
import states


class ServiceStatusClient(ValidatingWSClient):
    """A websocket client that syncs the state of all known services.

    On creation it connects to the supervisor service and gets the
    current status of each known service.  Then it listens for
    change notifications and updates it internal map of service states.

    Each service is assigned a unique number based on the order in
    which it was registered.
    """

    def __init__(self, url, logger_name=__file__):
        """Constructor.

        Args:
            url (string): The URL of the websocket server that we want
                to connect to.
            logger_name (string): An optional name that errors are logged to
        """
        super(ServiceStatusClient, self).__init__(url, logger_name)

        self._state_lock = Lock()
        self.services = {}
        self._name_map = {}

        # Register callbacks for all of the status notifications
        self.add_message_type(command_formats.ServiceStatusChanged, self._on_status_change)
        self.add_message_type(command_formats.ServiceAdded, self._on_service_added)
        self.add_message_type(command_formats.HeartbeatReceived, self._on_heartbeat)
        self.start()

        with self._state_lock:
            self.services = self.sync_services()
            for i, name in enumerate(self.services.iterkeys()):
                self._name_map[i] = name

    def local_service(self, name_or_id):
        """Get the locally synced information for a service.

        Args:
            name_or_id (string or int): Either a short name for the service or
                a numeric id.

        Returns:
            ServiceState: the current state of the service synced locally
                at the time of the call.
        """

        with self._state_lock:
            if isinstance(name_or_id, int) or isinstance(name_or_id, long):
                if name_or_id not in self._name_map:
                    raise ArgumentError("Unknown ID used to look up service", id=name_or_id)

                name = self._name_map[name_or_id]
            else:
                name = name_or_id

            if name not in self.services:
                raise ArgumentError("Unknown service name", name=name)

            service = self.services[name]
            return copy(service)

    def local_services(self):
        """Get a map of id, name pairs for all of the known synced services.

        Returns:
            list (id, name): A list of tuples with id and service name
        """

        with self._state_lock:
            return [(x, y) for x, y in self._name_map.iteritems()]

    def sync_services(self):
        """Poll the current state of all services.

        Returns:
            dict: A dictionary mapping service name to service status
        """

        services = {}

        servs = self.list_services()
        for i, serv in enumerate(servs):
            info = self.service_info(serv)
            status = self.service_status(serv)
            status.update(info)

            services[serv] = states.ServiceState(info['short_name'], info['long_name'], info['preregistered'], i)
            services[serv].state = status['numeric_status']

        return services

    def list_services(self):
        """Get the current list of services from the server.

        Returns:
            list(string): A list of the short service names known
                to the supervisor
        """

        resp = self.send_command('list_services', {}, timeout=5.0)
        return resp['payload']['services']

    def send_heartbeat(self, name):
        """Send a heartbeat for a service.

        Args:
            name (string): The name of the service to send a heartbeat for
        """

        resp = self.send_command('heartbeat', {'name': name}, timeout=5.0)
        if resp['success'] is not True:
            raise ArgumentError("Unknown service name", name=name)

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

        resp = self.send_command('query_info', {'name': name}, timeout=5.0)

        if resp['success'] is not True:
            raise ArgumentError("Unknown service name", name=name)

        return resp['payload']

    def update_state(self, name, state):
        """Update the state for a service.

        Args:
            name (string): The name of the service
            state (int): The new state of the service
        """

        resp = self.send_command('update_state', {'name': name, 'new_status': state}, timeout=5.0)
        if resp['success'] is not True:
            raise ArgumentError("Error updating service state", reason=resp['reason'])

    def service_status(self, name):
        """Pull the current status of a service by name.

        Returns:
            dict: A dictionary of service status
        """

        resp = self.send_command('query_status', {'name': name}, timeout=5.0)

        if resp['success'] is not True:
            raise ArgumentError("Unknown service name", name=name)

        return resp['payload']

    def register_service(self, short_name, long_name):
        """Register a new service with the service manager.

        Args:
            short_name (string): A unique short name for this service that functions
                as an id
            long_name (strign): A user facing name for this service

        Raises:
            ArgumentError: if the short_name is already taken
        """

        resp = self.send_command('register_service', {'name': short_name, 'long_name': long_name})

        if resp['success'] is not True:
            raise ArgumentError("Service name already registered", short_name=short_name)

    def _on_status_change(self, update):
        """Update a service that has its status updated."""

        info = update['payload']
        new_number = info['new_status']
        name = update['name']

        with self._state_lock:
            if name not in self.services:
                return

            self.services[name].state = new_number

    def _on_service_added(self, update):
        """Add a new service."""

        info = update['payload']
        name = info['short_name']

        with self._state_lock:
            if name in self.services:
                return

            new_id = len(self.services)
            serv = states.ServiceState(name, info['long_name'], info['preregistered'], new_id)
            self.services[name] = serv
            self._name_map[new_id] = name

    def _on_heartbeat(self, update):
        """Receive a new heartbeat for a service."""

        name = update['name']

        with self._state_lock:
            if name not in self.services:
                return

            self.services[name].heartbeat()
