"""A wrapper class that turns an AbstractDeviceAdapter into a legacy DeviceAdapter.

This allows modern AbstractDeviceAdapter classes to be used inside
AdapterStream so that they can be used by the synchronous HardwareManager.
"""

import asyncio
import logging
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities import SharedLoop

from .abstract import AbstractDeviceAdapter
from .legacy import DeviceAdapter
from ...exceptions import (DeviceAdapterError, RPCInvalidIDError,
                           TileNotFoundError, RPCNotFoundError,
                           RPCErrorCode, BusyRPCResponse)
from ...virtual import pack_rpc_response

_MISSING = object()


class SynchronousLegacyWrapper(DeviceAdapter):
    """Provide a legacy synchronous API on top of an AbstractDeviceAdapter."""

    MAX_ADAPTER_STARTUP_TIME = 10.0

    def __init__(self, adapter: AbstractDeviceAdapter, loop=SharedLoop):
        super(SynchronousLegacyWrapper, self).__init__()

        if not isinstance(adapter, AbstractDeviceAdapter):
            raise ArgumentError("DeviceAdapterLegacyWrapper created from object "
                                "not a subclass of AbstractDeviceAdapter", adapter=adapter)

        self._adapter = adapter
        self._loop = loop
        self._logger = logging.getLogger(__name__)

        # Synchronously start the adapter and block until it is started
        future = self._loop.launch_coroutine(self._adapter.start())
        future.result(SynchronousLegacyWrapper.MAX_ADAPTER_STARTUP_TIME)

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
                func(self.id, event, event.get('validity_period', 60))
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
                func(self.id, conn_id)
        else:
            raise ArgumentError("Unknown callback type {}".format(name))

        self._adapter.register_monitor([None], events, callback)

    def can_connect(self):
        return self._adapter.can_connect()

    def periodic_callback(self):
        """Periodic callback to allow adapter to process events.

        This is a no-op on asynchronous device adapters since they are able to
        run their own periodic callbacks inside the background event loop.
        """

    def stop_sync(self):
        future = self._loop.launch_coroutine(self._adapter.stop())
        return self._format_future(future)

    def connect_async(self, conn_id, connection_string, callback):
        """Asynchronously connect to a device."""

        future = self._loop.launch_coroutine(self._adapter.connect(conn_id, connection_string))
        future.add_done_callback(lambda x: self._callback_future(conn_id, x, callback))

    def disconnect_async(self, conn_id, callback):
        """Asynchronously disconnect from a device."""

        future = self._loop.launch_coroutine(self._adapter.disconnect(conn_id))
        future.add_done_callback(lambda x: self._callback_future(conn_id, x, callback))

    def open_interface_async(self, conn_id, interface, callback, connection_string=None):
        """Asynchronously connect to a device."""

        future = self._loop.launch_coroutine(self._adapter.open_interface(conn_id, interface))
        future.add_done_callback(lambda x: self._callback_future(conn_id, x, callback))

    def probe_async(self, callback):
        """Asynchronously connect to a device."""

        future = self._loop.launch_coroutine(self._adapter.probe())
        future.add_done_callback(lambda x: self._callback_future(None, x, callback))

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device."""

        future = self._loop.launch_coroutine(self._adapter.send_rpc(conn_id, address, rpc_id, payload, timeout))

        def format_response(future):
            payload = None
            exception = future.exception()
            rpc_status = None
            rpc_response = b''
            failure = None
            success = True

            if exception is None:
                payload = future.result()
                rpc_status, rpc_response = pack_rpc_response(payload, exception)
            elif isinstance(exception, (RPCInvalidIDError, TileNotFoundError, RPCNotFoundError,
                                        RPCErrorCode, BusyRPCResponse)):
                rpc_status, rpc_response = pack_rpc_response(payload, exception)
            else:
                success = False
                failure = str(exception)

            callback(conn_id, self.id, success, failure, rpc_status, rpc_response)

        future.add_done_callback(format_response)

    def debug_async(self, conn_id, cmd_name, cmd_args, progress_callback, callback):
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
            callback (callable): The callback that should be called when finished.
        """

        def monitor_callback(_conn_string, _conn_id, _event_name, event):
            if event.get('operation') != 'debug':
                return

            progress_callback(event.get('finished'), event.get('total'))

        async def _install_monitor():
            try:
                conn_string = self._adapter._get_property(conn_id, 'connection_string')
                return self._adapter.register_monitor([conn_string], ['progress'], monitor_callback)
            except:  #pylint:disable=bare-except;This is a legacy shim that must always ensure it doesn't raise.
                self._logger.exception("Error installing debug progress monitor")
                return None

        monitor_id = self._loop.run_coroutine(_install_monitor())
        if monitor_id is None:
            callback(conn_id, self.id, False, 'could not install progress monitor', None)
            return

        future = self._loop.launch_coroutine(self._adapter.debug(conn_id, cmd_name, cmd_args))

        def format_response(future):
            ret_val = None
            success = True
            failure = None
            if future.exception() is None:
                ret_val = future.result()
            else:
                success = False
                failure = str(future.exception())

            self._adapter.remove_monitor(monitor_id)
            callback(conn_id, self.id, success, ret_val, failure)

        future.add_done_callback(format_response)

    def send_script_async(self, conn_id, data, progress_callback, callback):
        """Asynchronously send a script to the device."""

        def monitor_callback(_conn_string, _conn_id, _event_name, event):
            if event.get('operation') != 'script':
                return

            progress_callback(event.get('finished'), event.get('total'))

        async def _install_monitor():
            try:
                conn_string = self._adapter._get_property(conn_id, 'connection_string')
                return self._adapter.register_monitor([conn_string], ['progress'], monitor_callback)
            except:  #pylint:disable=bare-except;This is a legacy shim that must always ensure it doesn't raise.
                self._logger.exception("Error installing script progress monitor")
                return None

        monitor_id = self._loop.run_coroutine(_install_monitor())
        if monitor_id is None:
            callback(conn_id, self.id, False, 'could not install progress monitor')
            return

        future = self._loop.launch_coroutine(self._adapter.send_script(conn_id, data))
        future.add_done_callback(lambda x: self._callback_future(conn_id, x, callback, monitors=[monitor_id]))

    def _format_exception(self, exception):
        if isinstance(exception, DeviceAdapterError):
            reason = exception.reason
        elif isinstance(exception, asyncio.TimeoutError):
            reason = "operation timed out"
        else:
            self._logger.error("Unknown exception during AbstractDeviceAdapter operation: %s", exception)
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

    def _callback_future(self, conn_id, future, callback, monitors=None):
        info = self._format_future(future)

        if monitors is not None:
            for monitor in monitors:
                self._adapter.remove_monitor(monitor)

        if conn_id is not None:
            callback(conn_id, self.id, info.get('success'), info.get('failure_reason'))
        else:
            callback(self.id, info.get('success'), info.get('failure_reason'))
