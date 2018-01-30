import threading
from iotile.core.exceptions import ArgumentError

MISSING = object()

class DeviceAdapter(object):
    """Classes that encapsulate access to IOTile devices over a particular communication channel

    Subclasses of DeviceAdapter implement concrete access channels over which IOTile devices
    can be controlled and send data. Examples area a bluetooth low energy communication channel
    or USB.  In order to fit into the rest of the IOTile tooling systems, only a few functions
    need to be implemented in a DeviceAdapter as shown below.  At its core, DeviceAdapters need
    to be able to connect/discconect from a device, open/close an interface on the device, send RPCs
    and send scripts.

    The interface to a DeviceAdapter is:
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

    probe_async
    probe_sync

    debug_async
    debug_sync

    periodic_callback
    can_connect

    stop_sync

    Subclasses only need to override the '_async' versions of each call.  The synchronous versions will
    be automatically functional using the '_async' versions provided that the '_async' version not use
    multiprocessing to invoke its callback, i.e. it should use multithreading since the default synchronous
    adapter function needs a shared memory lock.

    periodic_callback should be a non-blocking callback that is invoked periodically to allow
    the DeviceAdapter to maintain its internal state.

    Additionally you can register callbacks that will be called in the following circumstances:

    on_disconnect: called when the device disconnects unexpectedly
        Signature of on_disconnect should be on_disconnect(adapter_id, connection_id)
    on_report: called when the device has streamed a complete sensor graph report
        Signature of on_report should be on_report(connection_id, report),
        where report is a subclass of IOTileReport.
    on_scan: called when this device is seen during a scan of this communication channel
        Signature of on_scan should be on_scan(adapter_id, device_info, expiration_interval)
    on_trace: called when the device has received tracing data, which is an unstructured string
        of bytes.  Signature of on_trace should be on_trace(connection_id, trace_data),
        where trace_data is a bytearray.
    """

    def __init__(self):
        self.id = -1

        self.callbacks = {}
        self.callbacks['on_scan'] = set()
        self.callbacks['on_disconnect'] = set()
        self.callbacks['on_report'] = set()
        self.callbacks['on_trace'] = set()
        self.config = {}

    def set_id(self, adapter_id):
        """Set an ID that this adapater uses to identify itself when making callbacks
        """

        self.id = adapter_id

    def set_config(self, name, value):
        """Set a config value for this adapter by name

        Args:
            name (string): The name of the config variable
            value (object): The value of the config variable
        """

        self.config[name] = value

    def get_config(self, name, default=MISSING):
        """Get a config value from this adapter by name

        Args:
            name (string): The name of the config variable
            default (object): The default value to return if config is not found

        Returns:
            object: the value associated with the name

        Raises:
            ArgumentError: if the name is not found and no default is supplied
        """

        res = self.config.get(name, default)
        if res is MISSING:
            raise ArgumentError("Could not find config value by name and no default supplied", name=name)

        return res

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

        def connect_done(callback_connid, callback_adapterid, callback_success, failure_reason):
            calldone.set()
            results['success'] = callback_success
            results['failure_reason'] = failure_reason

        self.connect_async(connection_id, connection_string, connect_done)
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

        The interface parameter must be one of (rpc, script, streaming,
        tracing, debug).  Not all interfaces will be supported by all
        DeviceAdapters.

        Args:
            interface (string): The interface to open
            conn_id (int): A unique identifer that will refer to this connection
            callback (callable):  A callback that will be called as
                callback(conn_id, adapter_id, success, failure_reason)
        """

        if interface not in set(["rpc", "script", "streaming", "tracing", "debug"]):
            callback(conn_id, self.id, False, "invalid interface name in call to open_interface_async")
            return

        if interface == "rpc":
            self._open_rpc_interface(conn_id, callback)
        elif interface == 'script':
            self._open_script_interface(conn_id, callback)
        elif interface == 'streaming':
            self._open_streaming_interface(conn_id, callback)
        elif interface == 'tracing':
            self._open_tracing_interface(conn_id, callback)
        elif interface == 'debug':
            self._open_debug_interface(conn_id, callback)
        else:
            callback(conn_id, self.id, False, "interface not supported yet")

    def open_interface_sync(self, conn_id, interface):
        """Asynchronously open an interface to this IOTile device

        interface must be one of (rpc, script, streaming, tracing, debug)

        Args:
            interface (string): The interface to open
            conn_id (int): A unique identifer that will refer to this connection

        Returns:
            dict: A dictionary with four elements
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

    def probe_async(self, callback):
        """Probe for visible devices connected to this DeviceAdapter.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        callback(self.id, False, "Probe is not supported on this adapter")

    def probe_sync(self):
        """Synchronously probe for devices on this adapter."""

        done = threading.Event()
        result = {}

        def probe_done(adapter_id, status, reason):
            result['success'] = status
            result['failure_reason'] = reason
            done.set()

        self.probe_async(probe_done)
        done.wait()

        return result

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        callback(conn_id, self.id, False, 'RPCs are not supported on this adapter', None, None)

    def send_rpc_sync(self, conn_id, address, rpc_id, payload, timeout):
        """Synchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute

        Returns:
            dict: A dictionary with four elements
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        done = threading.Event()
        result = {}

        def send_rpc_done(conn_id, adapter_id, status, reason, rpc_status, resp_payload):
            result['success'] = status
            result['failure_reason'] = reason
            result['status'] = rpc_status
            result['payload'] = resp_payload

            done.set()

        self.send_rpc_async(conn_id, address, rpc_id, payload, timeout, send_rpc_done)
        done.wait()

        return result

    def debug_async(self, conn_id, cmd_name, cmd_args, progress_callback, callback):
        """Asynchronously complete a named debug command.

        The command name and arguments are passed to the underlying device adapter
        and interpreted there.  If the command is long running, progress_callback
        may be used to provide status updates.  Callback is called when the command
        has finished.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            cmd_name (string): the name of the debug command we want to invoke
            cmd_args (dict): any arguments that we want to send with this command.
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished the debug command, called as:
                callback(connection_id, adapter_id, success, retval, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'retval': A command specific dictionary of return value information
        """

        callback(conn_id, self.id, False, None, "Debug commands are not supported by this DeviceAdapter")

    def debug_sync(self, conn_id, cmd_name, cmd_args, progress_callback):
        """Asynchronously complete a named debug command.

        The command name and arguments are passed to the underlying device adapter
        and interpreted there.  If the command is long running, progress_callback
        may be used to provide status updates.  Callback is called when the command
        has finished.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            cmd_name (string): the name of the debug command we want to invoke
            cmd_args (dict): any arguments that we want to send with this command.
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
        """

        done = threading.Event()
        result = {}

        def _debug_done(conn_id, adapter_id, success, retval, reason):
            result['success'] = success
            result['failure_reason'] = reason
            result['return_value'] = retval

            done.set()

        self.debug_async(conn_id, cmd_name, cmd_args, progress_callback, _debug_done)
        done.wait()

        return result

    def send_script_async(self, conn_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        callback(conn_id, self.id, False, 'Sending scripts is not supported by this device adapter')

    def send_script_sync(self, conn_id, data, progress_callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)

        Returns:
            dict: a dict with the following two entries set
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        done = threading.Event()
        result = {}

        def send_script_done(conn_id, adapter_id, status, reason):
            result['success'] = status
            result['failure_reason'] = reason

            done.set()

        self.send_script_async(conn_id, data, progress_callback, send_script_done)
        done.wait()

        return result
