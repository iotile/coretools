import threading
import queue
import logging
from .timeout import TimeoutInterval
from iotile.core.exceptions import ArgumentError


class ConnectionAction:
    """A generic action handled internally by ConnectionManager

    Args:
        action (string): The action to take
        data (dict): Any assoicated data
        synchronous (bool): Whether the caller is synchronously waiting
            for the result.
        timeout (float): The maximum amount of time that should occur
            before timing this action out.
    """

    def __init__(self, action, data, timeout=5.0, sync=False):
        self.action = action
        self.data = data
        self.sync = sync
        self.timeout = TimeoutInterval(timeout)

        if self.sync:
            self.done = threading.Event()
        else:
            self.done = None


class ConnectionManager(threading.Thread):
    """A class that manages connection states and transitions.

    ConnectionManager presents a nonblocking interface that is designed
    to work with DeviceAdapter.  It handles maintaining an internal dictionary
    of currently active connections and a worker thread that processes
    requested changes to those connections.  All work is synchronized
    through requests to the worker thread.

    A connection can be in one of 4 macrostates:
        disconnected: There is no connection
        connecting: The connection has been started but has not yet entered
            a fully connected state
        idle: The connection is connected and idle
        in_progress: An operation is in progress on the connection
        disconnecting: The connection has started the disconnect process
        but has not finished it yet.

    The user of ConnectionManager is free to create their own microstates if
    the actions required to, e.g., connect to a device require a sequence
    of actions.

    Each connection has a user managed context associated with it that can be used
    to track data about the connection and an internal identifier that can be used
    to retrieve a connection's user context along with an integer connection_id.

    ConnectionManager just enforces that state transitions only happen in
    the following ways:
        nonexistent -> connecting -> idle <--> in_progress <--> idle -> disconnecting -> nonexistant

    ConnectionManager will fail a request that does not follow the above pattern.
    """

    Disconnected = 0
    Connecting = 1
    Idle = 2
    InProgress = 3
    Disconnecting = 4

    def __init__(self, adapter_id):
        """Constructor.

        Args:
            adapter_id (int): Since the ConnectionManager responds to callbacks on behalf
                of a DeviceAdapter, it needs to know what adapter_id to send with the
                callbacks.
        """

        super(ConnectionManager, self).__init__()

        self.id = adapter_id
        self._stop_event = threading.Event()
        self._actions = queue.Queue()
        self._connections = {}
        self._int_connections = {}
        self._data_lock = threading.Lock()

        # Our thread should be a daemon so that we don't block exiting the program if we hang
        self.daemon = True

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())
        self._logger.setLevel(logging.INFO)

    def run(self):
        while True:
            try:
                if self._stop_event.is_set():
                    break

                # Check if we should time anything out
                self._check_timeouts()

                try:
                    action = self._actions.get(timeout=0.1)
                except queue.Empty:
                    continue

                handler_name = '_{}_action'.format(action.action)

                if not hasattr(self, handler_name):
                    self._logger.error("Ignoring unknown action in ConnectionManager: %s", action.action)
                    continue

                handler = getattr(self, handler_name)
                handler(action)

                if action.sync:
                    action.done.set()
            except Exception:
                self._logger.exception('Exception processing event in ConnectionManager')

    def stop(self):
        try:
            self._stop_event.set()
            self.join(5.0)
        except RuntimeError:
            self._logger.warn("Could not stop connection manager thread, killing it on exit in a dirty fashion")

    def get_connections(self):
        """Get a list of all open connections

        Note that these connections can close at any time, so this cannot
        be relied upon to be valid at any point after this function returns

        Returns:
            int[]: A list of integer connection ids
        """

        return self._connections.keys()

    def get_context(self, conn_or_int_id):
        """Get the context for a connection by either conn_id or internal_id

        Args:
            conn_or_int_id (int, string): The external integer connection id or
                and internal string connection id

        Returns:
            dict: The context data associated with that connection or None if it cannot
                be found.

        Raises:
            ArgumentError: When the key is not found in the list of active connections
                or is invalid.
        """

        key = conn_or_int_id
        if isinstance(key, str):
            table = self._int_connections
        elif isinstance(key, int):
            table = self._connections
        else:
            raise ArgumentError("You must supply either an int connection id or a string internal id to _get_connection_state", id=key)

        try:
            data = table[key]
        except KeyError:
            raise ArgumentError("Could not find connection by id", id=key)

        return data['context']

    def get_connection_id(self, conn_or_int_id):
        """Get the connection id.

        Args:
            conn_or_int_id (int, string): The external integer connection id or
                and internal string connection id

        Returns:
            dict: The context data associated with that connection or None if it cannot
                be found.

        Raises:
            ArgumentError: When the key is not found in the list of active connections
                or is invalid.
        """

        key = conn_or_int_id
        if isinstance(key, str):
            table = self._int_connections
        elif isinstance(key, int):
            table = self._connections
        else:
            raise ArgumentError("You must supply either an int connection id or a string internal id to _get_connection_state", id=key)

        try:
            data = table[key]
        except KeyError:
            raise ArgumentError("Could not find connection by id", id=key)

        return data['conn_id']

    def _get_connection(self, conn_or_int_id):
        """Get the data for a connection by either conn_id or internal_id

        Args:
            conn_or_int_id (int, string): The external integer connection id or
                and internal string connection id

        Returns:
            dict: The context data associated with that connection or None if it cannot
                be found.

        Raises:
            ArgumentError: When the key is not found in the list of active connections
                or is invalid.
        """

        key = conn_or_int_id
        if isinstance(key, str):
            table = self._int_connections
        elif isinstance(key, int):
            table = self._connections
        else:
            return None

        try:
            data = table[key]
        except KeyError:
            return None

        return data

    def _get_connection_state(self, conn_or_int_id):
        """Get a connection's state by either conn_id or internal_id

        This routine must only be called from the internal worker thread.

        Args:
            conn_or_int_id (int, string): The external integer connection id or
                and internal string connection id
        """

        key = conn_or_int_id
        if isinstance(key, str):
            table = self._int_connections
        elif isinstance(key, int):
            table = self._connections
        else:
            raise ArgumentError("You must supply either an int connection id or a string internal id to _get_connection_state", id=key)

        if key not in table:
            return self.Disconnected

        data = table[key]
        return data['state']

    def _check_timeouts(self):
        """Check if any operations in progress need to be timed out

        Adds the corresponding finish action that fails the request due to a
        timeout.
        """

        for conn_id, data in self._connections.items():
            if 'timeout' in data and data['timeout'].expired:
                if data['state'] == self.Connecting:
                    self.finish_connection(conn_id, False, 'Connection attempt timed out')
                elif data['state'] == self.Disconnecting:
                    self.finish_disconnection(conn_id, False, 'Disconnection attempt timed out')
                elif data['state'] == self.InProgress:
                    if data['microstate'] == 'rpc':
                        self.finish_operation(conn_id, False, 'RPC timed out without response', None, None)
                    elif data['microstate'] == 'open_interface':
                        self.finish_operation(conn_id, False, 'Open interface request timed out')

    def begin_connection(self, conn_id, internal_id, callback, context, timeout):
        """Asynchronously begin a connection attempt

        Args:
            conn_id (int): The external connection id
            internal_id (string): An internal identifier for the connection
            callback (callable): The function to be called when the connection
                attempt finishes
            context (dict): Additional information to associate with this context
            timeout (float): How long to allow this connection attempt to proceed
                without timing it out
        """

        data = {
            'callback': callback,
            'connection_id': conn_id,
            'internal_id': internal_id,
            'context': context
        }

        action = ConnectionAction('begin_connection', data, timeout=timeout, sync=False)
        self._actions.put(action)

    def finish_connection(self, conn_or_internal_id, successful, failure_reason=None):
        """Finish a conntection attempt

        Args:
            conn_or_internal_id (string, int): Either an integer connection id or a string
                internal_id
            successful (bool): Whether this connection attempt was successful
            failure_reason (string): If this connection attempt failed, an optional reason
                for the failure.
        """

        data = {
            'id': conn_or_internal_id,
            'success': successful,
            'reason': failure_reason
        }

        action = ConnectionAction('finish_connection', data, sync=False)
        self._actions.put(action)

    def _begin_connection_action(self, action):
        """Begin a connection attempt

        Args:
            action (ConnectionAction): the action object describing what we are
                connecting to
        """

        conn_id = action.data['connection_id']
        int_id = action.data['internal_id']
        callback = action.data['callback']

        # Make sure we are not reusing an id that is currently connected to something
        if self._get_connection_state(conn_id) != self.Disconnected:
            print(self._connections[conn_id])
            callback(conn_id, self.id, False, 'Connection ID is already in use for another connection')
            return

        if self._get_connection_state(int_id) != self.Disconnected:
            callback(conn_id, self.id, False, 'Internal ID is already in use for another connection')
            return

        conn_data = {
            'state': self.Connecting,
            'microstate': None,
            'conn_id': conn_id,
            'int_id': int_id,
            'callback': callback,
            'timeout': action.timeout,
            'context': action.data['context']
        }

        self._connections[conn_id] = conn_data
        self._int_connections[int_id] = conn_data

    def _finish_connection_action(self, action):
        """Finish a connection attempt

        Args:
            action (ConnectionAction): the action object describing what we are
                connecting to and what the result of the operation was
        """

        success = action.data['success']
        conn_key = action.data['id']

        if self._get_connection_state(conn_key) != self.Connecting:
            print("Invalid finish_connection action on a connection whose state is not Connecting, conn_key=%s" % str(conn_key))
            return

        # Cannot be None since we checked above to make sure it exists
        data = self._get_connection(conn_key)
        callback = data['callback']

        conn_id = data['conn_id']
        int_id = data['int_id']

        if success is False:
            reason = action.data['reason']
            if reason is None:
                reason = "No reason was given"

            del self._connections[conn_id]
            del self._int_connections[int_id]
            callback(conn_id, self.id, False, reason)
        else:
            data['state'] = self.Idle
            data['microstate'] = None
            data['callback'] = None
            callback(conn_id, self.id, True, None)

    def unexpected_disconnect(self, conn_or_internal_id):
        """Notify that there was an unexpected disconnection of the device.

        Any in progress operations are canceled cleanly and the device is transitioned
        to a disconnected state.

        Args:
            conn_or_internal_id (string, int): Either an integer connection id or a string
                internal_id
        """

        data = {
            'id': conn_or_internal_id
        }

        action = ConnectionAction('force_disconnect', data, sync=False)
        self._actions.put(action)

    def begin_disconnection(self, conn_or_internal_id, callback, timeout):
        """Begin a disconnection attempt

        Args:
            conn_or_internal_id (string, int): Either an integer connection id or a string
                internal_id
            callback (callable): Callback to call when this disconnection attempt either
                succeeds or fails
            timeout (float): How long to allow this connection attempt to proceed
                without timing it out (in seconds)
        """

        data = {
            'id': conn_or_internal_id,
            'callback': callback
        }

        action = ConnectionAction('begin_disconnection', data, timeout=timeout, sync=False)
        self._actions.put(action)

    def _force_disconnect_action(self, action):
        """Forcibly disconnect a device.

        Args:
            action (ConnectionAction): the action object describing what we are
                forcibly disconnecting
        """

        conn_key = action.data['id']
        if self._get_connection_state(conn_key) == self.Disconnected:
            return

        data = self._get_connection(conn_key)

        # If there are any operations in progress, cancel them cleanly
        if data['state'] == self.Connecting:
            callback = data['callback']
            callback(False, 'Unexpected disconnection')
        elif data['state'] == self.Disconnecting:
            callback = data['callback']
            callback(True, None)
        elif data['state'] == self.InProgress:
            callback = data['callback']
            if data['microstate'] == 'rpc':
                callback(False, 'Unexpected disconnection', None, None)
            elif data['microstate'] == 'open_interface':
                callback(False, 'Unexpected disconnection')
            elif data['microstate'] == 'close_interface':
                callback(False, 'Unexpected disconnection')

        int_id = data['int_id']
        conn_id = data['conn_id']
        del self._connections[conn_id]
        del self._int_connections[int_id]

    def _begin_disconnection_action(self, action):
        """Begin a disconnection attempt

        Args:
            action (ConnectionAction): the action object describing what we are
                connecting to and what the result of the operation was
        """

        conn_key = action.data['id']
        callback = action.data['callback']

        if self._get_connection_state(conn_key) != self.Idle:
            callback(conn_key, self.id, False, 'Cannot start disconnection, connection is not idle')
            return

        # Cannot be None since we checked above to make sure it exists
        data = self._get_connection(conn_key)
        data['state'] = self.Disconnecting
        data['microstate'] = None
        data['callback'] = callback
        data['timeout'] = action.timeout

    def finish_disconnection(self, conn_or_internal_id, successful, failure_reason):
        """Finish a disconnection attempt

        Args:
            conn_or_internal_id (string, int): Either an integer connection id or a string
                internal_id
            successful (bool): Whether this connection attempt was successful
            failure_reason (string): If this connection attempt failed, an optional reason
                for the failure.
        """

        data = {
            'id': conn_or_internal_id,
            'success': successful,
            'reason': failure_reason
        }

        action = ConnectionAction('finish_disconnection', data, sync=False)
        self._actions.put(action)

    def _finish_disconnection_action(self, action):
        """Finish a disconnection attempt

        There are two possible outcomes:
        - if we were successful at disconnecting, we transition to disconnected
        - if we failed at disconnecting, we transition back to idle

        Args:
            action (ConnectionAction): the action object describing what we are
                disconnecting from and what the result of the operation was
        """

        success = action.data['success']
        conn_key = action.data['id']

        if self._get_connection_state(conn_key) != self.Disconnecting:
            self._logger.error("Invalid finish_disconnection action on a connection whose state is not Disconnecting, conn_key=%s", str(conn_key))
            return

        # Cannot be None since we checked above to make sure it exists
        data = self._get_connection(conn_key)
        callback = data['callback']

        conn_id = data['conn_id']
        int_id = data['int_id']

        if success is False:
            reason = action.data['reason']
            if reason is None:
                reason = "No reason was given"

            data['state'] = self.Idle
            data['microstate'] = None
            data['callback'] = None
            callback(conn_id, self.id, False, reason)
        else:
            del self._connections[conn_id]
            del self._int_connections[int_id]
            callback(conn_id, self.id, True, None)

    def begin_operation(self, conn_or_internal_id, op_name, callback, timeout):
        """Begin an operation on a connection

        Args:
            conn_or_internal_id (string, int): Either an integer connection id or a string
                internal_id
            op_name (string): The name of the operation that we are starting (stored in
                the connection's microstate)
            callback (callable): Callback to call when this disconnection attempt either
                succeeds or fails
            timeout (float): How long to allow this connection attempt to proceed
                without timing it out (in seconds)
        """

        data = {
            'id': conn_or_internal_id,
            'callback': callback,
            'timeout': timeout,
            'operation_name': op_name
        }

        action = ConnectionAction('begin_operation', data, sync=False)
        self._actions.put(action)

    def _begin_operation_action(self, action):
        """Begin an attempted operation.

        Args:
            action (ConnectionAction): the action object describing what we are
                operating on
        """

        conn_key = action.data['id']
        callback = action.data['callback']

        if self._get_connection_state(conn_key) != self.Idle:
            callback(conn_key, self.id, False, 'Cannot start operation, connection is not idle')
            return

        data = self._get_connection(conn_key)
        data['state'] = self.InProgress
        data['microstate'] = action.data['operation_name']
        data['callback'] = callback
        data['timeout'] = action.timeout

    def finish_operation(self, conn_or_internal_id, success, *args):
        """Finish an operation on a connection.

        Args:
            conn_or_internal_id (string, int): Either an integer connection id or a string
                internal_id
            success (bool): Whether the operation was successful
            failure_reason (string): Optional reason why the operation failed
            result (dict): Optional dictionary containing the results of the operation
        """

        data = {
            'id': conn_or_internal_id,
            'success': success,
            'callback_args': args
        }

        action = ConnectionAction('finish_operation', data, sync=False)
        self._actions.put(action)

    def _finish_operation_action(self, action):
        """Finish an attempted operation.

        Args:
            action (ConnectionAction): the action object describing the result
                of the operation that we are finishing
        """

        success = action.data['success']
        conn_key = action.data['id']

        if self._get_connection_state(conn_key) != self.InProgress:
            self._logger.error("Invalid finish_operation action on a connection whose state is not InProgress, conn_key=%s", str(conn_key))
            return

        # Cannot be None since we checked above to make sure it exists
        data = self._get_connection(conn_key)
        callback = data['callback']
        conn_id = data['conn_id']
        args = action.data['callback_args']

        data['state'] = self.Idle
        data['microstate'] = None

        callback(conn_id, self.id, success, *args)
