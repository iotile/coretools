"""An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface
"""

from builtins import str
from future.utils import viewitems
from copy import deepcopy
import queue
from .cmdstream import CMDStream
import datetime
import time
from iotile.core.exceptions import HardwareError, ArgumentError
from iotile.core.utilities.typedargs import iprint
from iotile.core.hw.reports import BroadcastReport


class AdapterCMDStream(CMDStream):
    """An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface

    DeviceAdapters have a more generic interface that is not restricted to exclusive use in an online
    fashion by a single user at a time.  This class implements the CMDStream interface on top of a
    DeviceAdapter.

    Args:
        adapter (DeviceAdapter): the DeviceAdatper that we should use to create this CMDStream
        port (string): the name of the port that we should connect through
        connection_string (string): A DeviceAdapter specific string specifying a device that we
            should immediately connect to
        record (string): The path to a file that we should use to record everything sent down
            this CMDStream
    """

    def __init__(self, adapter, port, connection_string, record=None):
        self.adapter = adapter
        self._scanned_devices = {}
        self._reports = None
        self._broadcast_reports = None
        self._traces = None
        self.connection_interrupted = False

        self.adapter.add_callback('on_scan', self._on_scan)
        self.adapter.add_callback('on_report', self._on_report)
        self.adapter.add_callback('on_trace', self._on_trace)
        self.adapter.add_callback('on_disconnect', self._on_disconnect)

        self.start_time = time.time()
        self.min_scan = self.adapter.get_config('minimum_scan_time', 0.0)
        self.probe_required = self.adapter.get_config('probe_required', False)

        super(AdapterCMDStream, self).__init__(port, connection_string, record)

    def _on_scan(self, adapter_id, info, expiration_time):
        """Callback called when a new device is discovered on this CMDStream

        Args:
            adapter_id (int): An ID for the adapter that scanned the device
            info (dict): Information about the scanned device
            expiration_time (float): How long this device should stay around
        """

        device_id = info['uuid']
        infocopy = deepcopy(info)

        infocopy['expiration_time'] = datetime.datetime.now() + datetime.timedelta(seconds=expiration_time)
        self._scanned_devices[device_id] = infocopy

    def _on_disconnect(self, adapter_id, connection_id):
        """Callback when a device is disconnected unexpectedly.

        Args:
            adapter_id (int): An ID for the adapter that was connected to the device
            connection_id (int): An ID for the connection that has become disconnected
        """

        self.connection_interrupted = True

    def _scan(self, wait=None):
        """Return the devices that have been found for this device adapter.

        If the adapter indicates that we need to explicitly tell it to probe for devices, probe now.
        By default we return the list of seen devices immediately, however there are two cases where
        we will sleep here for a fixed period of time to let devices show up in our result list:

        - If we are probing then we wait for 'minimum_scan_time'
        - If we are told an explicit wait time that overrides everything and we wait that long
        """

        # Figure out how long and if we need to wait before returning our scan results
        wait_time = None
        elapsed = time.time() - self.start_time
        if elapsed < self.min_scan:
            wait_time = self.min_scan - elapsed

        # If we need to probe for devices rather than letting them just bubble up, start the probe
        # and then use our min_scan_time to wait for them to arrive via the normal _on_scan event
        if self.probe_required:
            self.adapter.probe_sync()
            wait_time = self.min_scan

        # If an explicit wait is specified that overrides everything else
        if wait is not None:
            wait_time = wait

        if wait_time is not None:
            time.sleep(wait_time)

        to_remove = set()

        now = datetime.datetime.now()

        for name, value in viewitems(self._scanned_devices):
            if value['expiration_time'] < now:
                to_remove.add(name)

        for name in to_remove:
            del self._scanned_devices[name]

        return self._scanned_devices.values()

    def _connect(self, uuid_value, wait=None):
        # If we can't see the device, scan to try to find it
        if uuid_value not in self._scanned_devices:
            self.scan(wait=wait)

        if uuid_value not in self._scanned_devices:
            raise HardwareError("Could not find device to connect to by UUID", uuid=uuid_value)

        connstring = self._scanned_devices[uuid_value]['connection_string']
        self._connect_direct(connstring)

        return connstring

    def _connect_direct(self, connection_string):
        res = self.adapter.connect_sync(0, connection_string)
        if not res['success']:
            self.adapter.periodic_callback()
            raise HardwareError("Could not connect to device", reason=res['failure_reason'], connection_string=connection_string)

        try:
            res = self.adapter.open_interface_sync(0, 'rpc')
        except Exception as exc:
            self.adapter.disconnect_sync(0)
            self.adapter.periodic_callback()
            raise HardwareError("Could not open RPC interface on device due to an exception", exception=str(exc))

        if not res['success']:
            self.adapter.disconnect_sync(0)
            self.adapter.periodic_callback()
            raise HardwareError("Could not open RPC interface on device", reason=res['failure_reason'], connection_string=connection_string)

    def _disconnect(self):

        # Close the streaming and tracing interfaces when we disconnect
        self._reports = None
        self._traces = None

        self.adapter.disconnect_sync(0)
        self.adapter.periodic_callback()

    def _try_reconnect(self):
        """Try to recover an interrupted connection."""

        try:
            if self.connection_interrupted:
                self._connect_direct(self.connection_string)
                self.connection_interrupted = False
                self.connected = True

                # Reenable streaming interface if that was open before as well
                if self._reports is not None:
                    res = self.adapter.open_interface_sync(0, 'streaming')
                    if not res['success']:
                        raise HardwareError("Could not open streaming interface to device", reason=res['failure_reason'])

                # Reenable tracing interface if that was open before as well
                if self._traces is not None:
                    res = self.adapter.open_interface_sync(0, 'tracing')
                    if not res['success']:
                        raise HardwareError("Could not open tracing interface to device", reason=res['failure_reason'])
        except HardwareError as exc:
            raise HardwareError("Device disconnected unexpectedly and we could not reconnect", reconnect_error=exc)

    def _send_rpc(self, address, rpc_id, payload, **kwargs):
        timeout = 3.0
        if 'timeout' in kwargs:
            timeout = float(kwargs['timeout'])

        # If our connection was interrupted before this RPC, try to recover it
        if self.connection_interrupted:
            self._try_reconnect()

        result = self.adapter.send_rpc_sync(0, address, rpc_id, payload, timeout)
        success = result['success']
        status = result['status']
        payload = result['payload']

        # Sometimes RPCs can cause the device to go offline, so try to reconnect to it.
        # For example, the RPC could cause the device to reset itself.
        if self.connection_interrupted:
            self._try_reconnect()

        if not success:
            raise HardwareError("Could not send RPC", reason=result['failure_reason'])

        self.adapter.periodic_callback()

        return status, payload

    def _send_highspeed(self, data, progress_callback):
        if isinstance(data, str) and not isinstance(data, bytes):
            raise ArgumentError("You must send bytes or bytearray to _send_highspeed", type=type(data))

        if not isinstance(data, bytes):
            data = bytes(data)

        self.adapter.send_script_sync(0, data, progress_callback)

    def _enable_streaming(self):
        self._reports = queue.Queue()
        res = self.adapter.open_interface_sync(0, 'streaming')
        if not res['success']:
            raise HardwareError("Could not open streaming interface to device", reason=res['failure_reason'])

        return self._reports

    def _enable_broadcasting(self):
        if self._broadcast_reports is not None:
            return

        self._broadcast_reports = queue.Queue()
        return self._broadcast_reports

    def _enable_debug(self, connection_string=None):
        res = self.adapter.open_interface_sync(0, 'debug', connection_string)
        if not res['success']:
            raise HardwareError("Could not open debug interface to device", reason=res['failure_reason'])

    def _debug_command(self, cmd, args, progress_callback=None):
        def _progress_callback(_finished, _total):
            pass

        res = self.adapter.debug_sync(0, cmd, args, progress_callback)
        if not res['success']:
            raise HardwareError("Could not execute debug command %s on device" % cmd, reason=res['failure_reason'])

        return res.get('return_value')

    def _enable_tracing(self):
        self._traces = queue.Queue()
        res = self.adapter.open_interface_sync(0, 'tracing')
        if not res['success']:
            raise HardwareError("Could not open tracing interface to device", reason=res['failure_reason'])

        return self._traces

    def _on_report(self, conn_id, report):
        if isinstance(report, BroadcastReport):
            if self._broadcast_reports is None:
                return

            self._broadcast_reports.put(report)
            return

        if self._reports is None:
            return

        self._reports.put(report)

    def _on_trace(self, conn_id, tracing_data):
        if self._traces is None:
            return

        self._traces.put(tracing_data)

    def _close(self):
        self.adapter.stop_sync()
