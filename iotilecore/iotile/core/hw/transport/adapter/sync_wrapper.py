"""A wrapper class that turns an AbstractDeviceAdapter into a legacy DeviceAdapter.

This allows modern AbstractDeviceAdapter classes to be used inside
AdapterStream so that they can be used by the synchronous HardwareManager.
"""

import asyncio
import logging
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities import SharedLoop

from .abstract import AbstractDeviceAdapter
from ...exceptions import DeviceAdapterError
from ...virtual import (RPCInvalidIDError, TileNotFoundError, RPCNotFoundError,
                        RPCErrorCode, pack_rpc_response)

_MISSING = object()


class SynchronousLegacyWrapper:
    """Provide a legacy synchronous API on top of an AbstractDeviceAdapter."""

    MAX_ADAPTER_STARTUP_TIME = 10.0

    def __init__(self, adapter: AbstractDeviceAdapter, loop=SharedLoop):
        if not isinstance(adapter, AbstractDeviceAdapter):
            raise ArgumentError("DeviceAdapterLegacyWrapper created from object "
                                "not a subclass of AbstractDeviceAdapter", adapter=adapter)

        self._adapter = adapter
        self._id = -1
        self._loop = loop
        self._logger = logging.getLogger(__name__)

        # Synchronously start the adapter and block until it is started
        future = self._loop.launch_coroutine(self._adapter.start())
        future.result(SynchronousLegacyWrapper.MAX_ADAPTER_STARTUP_TIME)

    @property
    def id(self):
        """The unique id of this adapter."""

        return self._id

    def set_id(self, adapter_id):
        """Set an ID that this adapter uses to identify itself when making callbacks.

        Args:
            adapter_id (int): The adapter id that will be included in all callbacks.
        """

        self._id = adapter_id

    def set_config(self, name, value):
        """Set a config value for this adapter by name

        Args:
            name (string): The name of the config variable
            value (object): The value of the config variable
        """

        self._adapter.set_config(name, value)

    def get_config(self, name, default=_MISSING):
        """Get a config value from this adapter by name

        Args:
            name (string): The name of the config variable
            default (object): The default value to return if config is not found

        Returns:
            object: the value associated with the name

        Raises:
            ArgumentError: if the name is not found and no default is supplied
        """

        value = self._adapter.get_config(name, default)
        if value is _MISSING:
            raise ArgumentError("Config value did not exist", name=name)

        return value

    def add_callback(self, name, func):
        """Add a callback when device events happen.

        Args:
            name (str): currently support 'on_scan' and 'on_disconnect'
            func (callable): the function that should be called
        """

        if name == 'on_scan':
            events = ['device_seen']
            def callback(_conn_string, _conn_id, _name, event):
                func(self._id, event, event.get('validity_period', 60))
        elif name == 'on_report':
            events = ['report', 'broadcast']
            def callback(_conn_string, conn_id, _name, event):
                func(conn_id, event)
        elif name == 'on_trace':
            events = ['trace']
            def callback(_conn_string, conn_id, _name, event):
                func(conn_id, event)
        elif name == 'on_disconnect':
            events = ['disconnection']
            def callback(_conn_string, conn_id, _name, _event):
                func(self._id, conn_id)
        else:
            raise ArgumentError("Unknown callback type {}".format(name))

        self._adapter.register_monitor([None], events, callback)

    def periodic_callback(self):
        """Periodic callback to allow adapter to process events.

        This is a no-op on asynchronous device adapters since they are able to
        run their own periodic callbacks inside the background event loop.
        """

    def stop_sync(self):
        future = self._loop.launch_coroutine(self._adapter.stop())
        return self._format_future(future)

    def connect_sync(self, conn_id, connection_string):
        """Synchronously connect to a device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.

        Returns:
            dict: A dictionary with two elements
                'success': a bool with the result of the connection attempt
                'failure_reason': a string with the reason for the failure if we failed
        """

        future = self._loop.launch_coroutine(self._adapter.connect(conn_id, connection_string))
        return self._format_future(future)

    def disconnect_sync(self, conn_id):
        """Synchronously disconnect from a connected device

        Args:
            conn_id (int): A unique identifier that will refer to this connection

        Returns:
            dict: A dictionary with two elements
                'success': a bool with the result of the connection attempt
                'failure_reason': a string with the reason for the failure if we failed
        """

        future = self._loop.launch_coroutine(self._adapter.disconnect(conn_id))
        return self._format_future(future)

    def open_interface_sync(self, conn_id, interface, connection_string=None):
        """Asynchronously open an interface to this IOTile device

        interface must be one of (rpc, script, streaming, tracing, debug)

        Args:
            interface (string): The interface to open
            conn_id (int): A unique identifier that will refer to this connection
            connection_string (string): An optional DeviceAdapter specific string that can
                be used to connect to a device using this DeviceAdapter.
        Returns:
            dict: A dictionary with two elements
                'success': a bool with the result of the connection attempt
                'failure_reason': a string with the reason for the failure if we failed
        """

        future = self._loop.launch_coroutine(self._adapter.open_interface(conn_id, interface, connection_string))
        return self._format_future(future)

    def probe_sync(self):
        """Synchronously probe for devices on this adapter."""

        future = self._loop.launch_coroutine(self._adapter.probe())

        if future.exception():
            try:
                future.result()
            except:
                self._logger.exception("Error probing")

        return self._format_future(future)

    def send_rpc_sync(self, conn_id, address, rpc_id, payload, timeout):
        """Synchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            address (int): the address of the tile that we wish to send the RPC to
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

        future = self._loop.launch_coroutine(self._adapter.send_rpc(conn_id, address, rpc_id, payload, timeout))

        payload = None
        exception = future.exception()
        if exception is None:
            payload = future.result()


        rpc_status, rpc_response = pack_rpc_response(payload, exception)

        return {
            'success': True,
            'failure_reason': None,
            'status': rpc_status,
            'payload': rpc_response
        }

    def debug_sync(self, conn_id, cmd_name, cmd_args, progress_callback):
        """Asynchronously complete a named debug command.

        The command name and arguments are passed to the underlying device adapter
        and interpreted there.  If the command is long running, progress_callback
        may be used to provide status updates.  Callback is called when the command
        has finished.

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            cmd_name (string): the name of the debug command we want to invoke
            cmd_args (dict): any arguments that we want to send with this command.
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
        """

        future = self._loop.launch_coroutine(self._adapter.debug(conn_id, cmd_name, cmd_args, progress_callback))
        if future.exception() is not None:
            return self._format_exception(future.exception())

        return {
            'success': True,
            'failure_reason': None,
            'return_value': future.result()
        }

    def send_script_sync(self, conn_id, data, progress_callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)

        Returns:
            dict: a dict with the following two entries set
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        future = self._loop.launch_coroutine(self._adapter.send_script(conn_id, data, progress_callback))
        return self._format_future(future)

    def _format_exception(self, exception):
        if isinstance(exception, DeviceAdapterError):
            reason = exception.reason
        elif isinstance(exception, asyncio.TimeoutError):
            reason = "operation timed out"
        else:
            self._logger.error("Unknown exception during AbstractDeviceAdapter operation")
            reason = "Unknown exception {}".format(exception)

        return {
            'success': False,
            'failure_reason': reason
        }

    def _format_future(self, future):
        exception = future.exception()
        if exception is not None:
            return self._format_exception(exception)

        return {
            'success': True,
            'failure_reason': None
        }
