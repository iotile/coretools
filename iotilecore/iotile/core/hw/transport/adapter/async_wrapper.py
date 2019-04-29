"""A wrapper class that turns a legacy DeviceAdapter into an AbstractDeviceAdapter.

The legacy adapter routines are run in a thread executor to provide a
non-blocking coroutine based api.  All callbacks from the legacy adapter are
translated to the corresponding event type appropriate and notified as events.

The periodic callback from the legacy adapter is called in a loop once per second
with the the periodic_callback itself running in an executor thread in case it
contains blocking operations.
"""

import asyncio
import logging
import functools
import concurrent.futures
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities import SharedLoop
from iotile.core.hw.reports import BroadcastReport
from .standard import StandardDeviceAdapter
from .legacy import DeviceAdapter
from ...exceptions import DeviceAdapterError
from ...virtual import unpack_rpc_response

_MISSING = object()


class AsynchronousModernWrapper(StandardDeviceAdapter):
    """Provide a modern coroutine API on top of a legacy DeviceAdapter."""

    def __init__(self, adapter, loop=SharedLoop):
        super(AsynchronousModernWrapper, self).__init__(loop=loop)

        if not isinstance(adapter, DeviceAdapter):
            raise ArgumentError("AsynchronousModernWrapper created from object "
                                "not a subclass of DeviceAdapter", adapter=adapter)

        self._adapter = adapter
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self._task = loop.add_task(None, name="LegacyAdapter (%s)" % adapter.__class__.__name__,
                                   finalizer=self.stop, stop_timeout=5.0)

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

    async def start(self):
        """Start the device adapter.

        See :meth:`AbstractDeviceAdapter.start`.
        """

        self._loop.add_task(self._periodic_loop, name="periodic task for %s" % self._adapter.__class__.__name__,
                            parent=self._task)

        self._adapter.add_callback('on_scan', functools.partial(_on_scan, self._loop, self))
        self._adapter.add_callback('on_report', functools.partial(_on_report, self._loop, self))
        self._adapter.add_callback('on_trace', functools.partial(_on_trace, self._loop, self))
        self._adapter.add_callback('on_disconnect', functools.partial(_on_disconnect, self._loop, self))

    async def stop(self, _task=None):
        """Stop the device adapter.

        See :meth:`AbstractDeviceAdapter.stop`.
        """

        self._logger.info("Stopping adapter wrapper")

        if self._task.stopped:
            return

        for task in self._task.subtasks:
            await task.stop()

        self._logger.debug("Stopping underlying adapter %s", self._adapter.__class__.__name__)
        await self._execute(self._adapter.stop_sync)

    def _execute(self, func, *args):
        return self._loop.get_loop().run_in_executor(self._executor, func, *args)

    async def _periodic_loop(self):
        while True:
            try:
                await self._execute(self._adapter.periodic_callback)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except:  #pylint:disable=bare-except;This is a background worker task that logs the error
                self._logger.exception("Error in periodic callback from device adapter")

    def can_connect(self):
        """Return whether this device adapter can accept another connection.

        We just forward the request to the underlying adapter and ask.

        See :meth:`AbstractDeviceAdapter.can_connect`.
        """

        return self._adapter.can_connect()

    async def connect(self, conn_id, connection_string):
        """Connect to a device.

        See :meth:`AbstractDeviceAdapter.connect`.
        """

        self._logger.info("Inside connect, conn_id=%d, conn_string=%s", conn_id, connection_string)

        try:
            self._setup_connection(conn_id, connection_string)

            resp = await self._execute(self._adapter.connect_sync, conn_id, connection_string)
            _raise_error(conn_id, 'connect', resp)
        except:
            self._teardown_connection(conn_id, force=True)
            raise

    async def disconnect(self, conn_id):
        """Disconnect from a connected device.

        See :meth:`AbstractDeviceAdapter.disconnect`.
        """

        resp = await self._execute(self._adapter.disconnect_sync, conn_id)
        _raise_error(conn_id, 'disconnect', resp)
        self._teardown_connection(conn_id, force=True)

    async def open_interface(self, conn_id, interface):
        """Open an interface on an IOTile device.

        See :meth:`AbstractDeviceAdapter.open_interface`.
        """

        resp = await self._execute(self._adapter.open_interface_sync, conn_id, interface)
        _raise_error(conn_id, 'open_interface', resp)

    async def close_interface(self, conn_id, interface):
        """Close an interface on this IOTile device.

        See :meth:`AbstractDeviceAdapter.close_interface`.
        """

        resp = await self._execute(self._adapter.close_interface_sync, conn_id, interface)
        _raise_error(conn_id, 'close_interface', resp)

    async def probe(self):
        """Probe for devices connected to this adapter.

        See :meth:`AbstractDeviceAdapter.probe`.
        """

        resp = await self._execute(self._adapter.probe_sync)
        _raise_error(None, 'probe', resp)

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Send an RPC to a device.

        See :meth:`AbstractDeviceAdapter.send_rpc`.
        """

        resp = await self._execute(self._adapter.send_rpc_sync, conn_id, address, rpc_id, payload, timeout)
        _raise_error(conn_id, 'send_rpc', resp)

        status = resp.get('status')
        payload = resp.get('payload')

        # This will raise an exception if needed based on status
        return unpack_rpc_response(status, payload, rpc_id, address)

    async def debug(self, conn_id, name, cmd_args):
        """Send a debug command to a device.

        See :meth:`AbstractDeviceAdapter.debug`.
        """

        progress_callback = functools.partial(_on_progress, self, 'debug', conn_id)

        resp = await self._execute(self._adapter.debug_sync, conn_id, name, cmd_args, progress_callback)
        _raise_error(conn_id, 'send_rpc', resp)

        return resp.get('return_value')

    async def send_script(self, conn_id, data):
        """Send a a script to a device.

        See :meth:`AbstractDeviceAdapter.send_script`.
        """

        progress_callback = functools.partial(_on_progress, self, 'script', conn_id)

        resp = await self._execute(self._adapter.send_script_sync, conn_id, data, progress_callback)
        _raise_error(conn_id, 'send_rpc', resp)


def _raise_error(conn_id, operation, resp):
    if resp['success'] is False:
        raise DeviceAdapterError(conn_id, operation, resp.get('failure_reason', "unknown failure reason"))


def _on_scan(_loop, adapter, _adapter_id, info, expiration_time):
    """Callback when a new device is seen."""

    info['validity_period'] = expiration_time
    adapter.notify_event_nowait(info.get('connection_string'), 'device_seen', info)


def _on_report(_loop, adapter, conn_id, report):
    """Callback when a report is received."""

    conn_string = None
    if conn_id is not None:
        conn_string = adapter._get_property(conn_id, 'connection_string')

    if isinstance(report, BroadcastReport):
        adapter.notify_event_nowait(conn_string, 'broadcast', report)
    elif conn_string is not None:
        adapter.notify_event_nowait(conn_string, 'report', report)
    else:
        adapter._logger.debug("Dropping report with unknown conn_id=%s", conn_id)


def _on_trace(_loop, adapter, conn_id, trace):
    """Callback when tracing data is received."""

    conn_string = adapter._get_property(conn_id, 'connection_string')
    if conn_string is None:
        adapter._logger.debug("Dropping trace data with unknown conn_id=%s", conn_id)
        return

    adapter.notify_event_nowait(conn_string, 'trace', trace)


def _on_disconnect(_loop, adapter, _adapter_id, conn_id):
    """Callback when a device disconnects unexpectedly."""

    conn_string = adapter._get_property(conn_id, 'connection_string')
    if conn_string is None:
        adapter._logger.debug("Dropping disconnect notification with unknown conn_id=%s", conn_id)
        return

    adapter._teardown_connection(conn_id, force=True)
    event = dict(reason='no reason passed from legacy adapter', expected=False)
    adapter.notify_event_nowait(conn_string, 'disconnection', event)


def _on_progress(adapter, operation, conn_id, done, total):
    """Callback when progress is reported."""

    conn_string = adapter._get_property(conn_id, 'connection_string')
    if conn_string is None:
        return

    adapter.notify_progress(conn_string, operation, done, total)
