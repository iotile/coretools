from ...exceptions import DeviceAdapterError

class PerConnectionDataMixin:
    """A mixin class for DeviceAdapters to track per-connection data."""

    def __init__(self):
        self._connections = {}
        self._reverse_connetions = {}

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
        self._reverse_connetions[conn_string] = conn_id

    def _teardown_connection(self, conn_id):
        if conn_id not in self._connections:
            raise DeviceAdapterError(conn_id, 'none', 'connection id torndown without being setup')

        conn_string = self._connections[conn_id]['connection_string']
        del self._connections[conn_id]
        del self._reverse_connetions[conn_string]

    def _get_conn_id(self, conn_string):
        return self._reverse_connetions.get(conn_string, None)
