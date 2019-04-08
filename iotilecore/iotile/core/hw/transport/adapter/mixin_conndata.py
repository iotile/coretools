"""Mixin for keeping track of per-connection data."""

from ...exceptions import DeviceAdapterError

#pylint:disable=too-few-public-methods;This is a mixin class
class PerConnectionDataMixin:
    """A mixin class for DeviceAdapters to track per-connection data.

    This class helps adapters comply with the requirement to be able to track
    per-connection information for internal usage as well as providing a
    reference implementation of :meth:`_get_conn_id`, which is needed to map
    connection_strings to connection_ids for the purposes of sending
    notifications attached to a connection.

    It is very simple and requires that your adapter's ``connect`` and ``disconnect``
    implementations call :meth:`_setup_connection` and :meth:`_teardown_connection`
    respectively in order to manage the connection metadata correctly.

    If you receive an unexpected disconnection event from a device, you must
    also call :meth:`_teardown_connection` as well to make sure the connection
    state is properly recorded.

    In any method that requires a valid open connection, you can just call
    :meth:`_ensure_connection` at the start of your implementation to fail correctly
    if the connection is no longer valid.
    """

    def __init__(self):
        self._connections = {}
        self._reverse_connections = {}

    def _get_property(self, conn_id, name):
        info = self._connections.get(conn_id)
        if info is None:
            raise DeviceAdapterError(conn_id, 'none', 'connection id does not exist')

        return info.get(name)

    def _track_property(self, conn_id, name, value):
        info = self._connections.get(conn_id)
        if info is None:
            raise DeviceAdapterError(conn_id, 'none', 'connection id does not exist')

        info[name] = value

    def _ensure_connection(self, conn_id, is_connected):
        if (conn_id in self._connections) != is_connected:
            raise DeviceAdapterError(conn_id, 'none', 'connection in wrong state')

    def _setup_connection(self, conn_id, conn_string):
        if conn_id in self._connections:
            raise DeviceAdapterError(conn_id, 'none', 'connection id setup twice')

        self._connections[conn_id] = dict(connection_string=conn_string)
        self._reverse_connections[conn_string] = conn_id

    def _teardown_connection(self, conn_id, force=False):
        if conn_id not in self._connections:
            if force:
                return

            raise DeviceAdapterError(conn_id, 'none', 'connection id torndown without being setup')

        conn_string = self._connections[conn_id]['connection_string']
        del self._connections[conn_id]
        del self._reverse_connections[conn_string]

    def _get_conn_id(self, conn_string):
        return self._reverse_connections.get(conn_string, None)
