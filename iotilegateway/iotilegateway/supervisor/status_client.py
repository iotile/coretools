"""A websocket client that replicates the state of the supervisor
"""

from iotile.core.utilities.validating_wsclient import ValidatingWSClient
import command_formats


class ServiceStatusClient(ValidatingWSClient):
    """A websocket client that syncs the state of all known services

    On creation it connects to the supervisor service and gets the
    current status of each known service.  Then it listens for
    change notifications and updates it internal map of service states.

    Each service is assigned a unique number based on the order in
    which it was registered.

    Args:
        url (string): The URL of the websocket server that we want
            to connect to.
        logger_name (string): An optional name that errors are logged to
    """

    def __init__(self, url, logger_name=__file__):
        super(ServiceStatusClient, self).__init__(url, logger_name)

        self.services = {}
        self._name_map = {}

        # Register callbacks for all of the status notifications
        #self.add_message_type(command_formats.ServiceStatusChanged, self._on_status_change)

        self.start()

    def sync_services(self):
        """Poll the current state of all services

        Returns:
            dict: A dictionary mapping service name to service status
        """

        # TODO Add synchronization of services here
        pass

    def pull_service_list(self):
        """Get the current list of services from the server

        Returns:
            list(string): A list of the short service names known
                to the supervisor
        """

        resp = self.send_command('list_services', {}, timeout=5.0)
        return resp['payload']['services']

    def pull_service_status(self, name):
        """Pull the current status of a service by name

        Returns:
            dict: A dictionary of service status
        """

        resp = self.send_command('query_status', {'name': name}, timeout=5.0)
        return resp['status']
