import threading

class DeviceAdapter(object):
    """Classes that encapsulate access to IOTile devices over a particular communication channel

    The interface to a DeviceAdapter is very simple:
    connect_async
    connect_sync

    disconnect_async
    disconnect_sync

    open_interface_async
    open_interface_sync

    close_interface_async
    close_interface_sync

    send_rpc_async
    send_rpc_sync

    send_script_async
    send_script_sync

    Additionally you can register callbacks that will be called in the following circumstances:

    on_disconnect: called when the device disconnects unexpectedly
    on_report: called when teh device has streamed a complete sensor graph report
    on_scan: called when this device is seen during a scan of this communication channel
    """

    def __init__(self):
        self.id = -1

        self.callbacks = {}
        self.callbacks['on_scan'] = set()
        self.callbacks['on_disconnect'] = set()
        self.callbacks['on_report'] = set()

    def set_id(self, adapter_id):
        """Set an ID that this adapater uses to identify itself when making callbacks
        """
        
        self.id = adapter_id

    def add_callback(self, name, func):
        """Add a callback when Device events happen

        Args:
            name (str): currently support 'on_scan' and 'on_disconnect'
            func (callable): the function that should be called
        """

        if name not in self.callbacks:
            raise ValueError("Unknown callback name: %s" % name)

        self.callbacks[name].add(func)

    def _trigger_callback(self, name, *args, **kwargs):
        for func in self.callbacks[name]:
            func(*args, **kwargs)

    def connect_async(self, connection_id, connection_string, callback):
        """Asynchronously connect to a device

        Args:
            connection_id (int): A unique identifer that will refer to this connection
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.
            callback (callable): A function that will be called when the connection attempt finishes as
                callback(conection_id, adapter_id, success: bool, failure_reason: string or None)
        """

        if callback is not None:
            callback(connection_id, self.id, False, "connect command is not supported in device adapter")

    def connect_sync(self, connection_id, connection_string):
        """Synchronously connect to a device

        Args:
            connection_id (int): A unique identifer that will refer to this connection
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.

        Returns:
            dict: A dictionary with two elements
                'success': a bool with the result of the connection attempt
                'failure_reaon': a string with the reason for the failure if we failed
        """

        calldone = threading.Event()
        results = {}

        def connection_callback(callback_connid, callback_adapterid, callback_success, failure_reason):
            calldone.set()
            results['success'] = callback_success
            results['failure_reason'] = failure_reason

        self.connect_async(connection_id, connection_string, connection_callback)
        calldone.wait()

        return results

    def disconnect_async(self, conn_id, callback):
        """Asynchronously disconnect from a connected device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            callback (callback): A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        callback(conn_id, self.id, False, "disconnect command is not supported in device adapter")

    def disconnect_sync(self, conn_id):
        """Synchronously disconnect from a connected device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
        
        Returns:
            dict: A dictionary with two elements
                'success': a bool with the result of the connection attempt
                'failure_reaon': a string with the reason for the failure if we failed
        """

        done = threading.Event()
        result = {}

        def disconnect_done(conn_id, adapter_id, status, reason):
            result['success'] = status
            result['failure_reason'] = reason
            done.set()

        self.disconnect_async(conn_id, disconnect_done)
        done.wait()

        return result

    def open_interface_async(self, conn_id, interface, callback):
        """Asynchronously open an interface to this IOTile device

        interface must be one of (rpc, script, streaming)

        Args:
            interface (string): The interface to open
            conn_id (int): A unique identifer that will refer to this connection 
            callback (callable):  A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if interface not in set(["rpc", "script", "streaming"]):
            callback(conn_id, self.id, False, "invalid interface name in call to open_interface_async")
            return

        if interface == "rpc":
            self._open_rpc_interface(conn_id, callback)
        else:
            callback(conn_id, self.id, False, "interface not supported yet")

    def open_interface_sync(self, conn_id, interface):
        """Asynchronously open an interface to this IOTile device

        interface must be one of (rpc, script, streaming)

        Args:
            interface (string): The interface to open
            conn_id (int): A unique identifer that will refer to this connection

        Returns:
            dict: A dictionary with two elements
                'success': a bool with the result of the connection attempt
                'failure_reaon': a string with the reason for the failure if we failed
        """

        done = threading.Event()
        result = {}

        def open_interface_done(conn_id, adapter_id, status, reason):
            result['success'] = status
            result['failure_reason'] = reason
            done.set()

        self.open_interface_async(conn_id, interface, open_interface_done)
        done.wait()

        return result
