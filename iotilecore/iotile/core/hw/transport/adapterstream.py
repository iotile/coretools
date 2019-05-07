"""An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface"""

from copy import deepcopy
import queue
from time import monotonic, sleep
from datetime import datetime
import binascii
import logging
import threading
from iotile.core.exceptions import HardwareError, ArgumentError
from iotile.core.utilities import SharedLoop
from ..exceptions import VALID_RPC_EXCEPTIONS
from ..virtual import unpack_rpc_response, pack_rpc_response
from .adapter import AbstractDeviceAdapter, AsynchronousModernWrapper, DeviceAdapter


class _RecordedRPC:
    """Internal helper class for saving recorded RPCs to csv files."""

    def __init__(self, connection, address, rpc_id, call):
        if isinstance(connection, bytes):
            connection = connection.decode('utf-8')

        self.connection = connection
        self.address = address
        self.rpc_id = rpc_id
        self.call = binascii.hexlify(call).decode('utf-8')

        self.status = -1
        self.start_stamp = None

        self.response = ""
        self.error = ""

        self.runtime = 0
        self._start_time = 0

    def start(self):
        """Mark the beginning of a recorded RPC."""

        self._start_time = monotonic()
        self.start_stamp = datetime.utcnow()

    def finish(self, status, response):
        """Mark the end of a recorded RPC."""

        self.response = binascii.hexlify(response).decode('utf-8')
        self.status = status
        self.runtime = monotonic() - self._start_time

    def serialize(self):
        """Convert this recorded RPC into a string."""

        return "{},{: <26},{:2d},{:#06x},{:#04x},{:5.0f},{: <40},{: <40},{}".\
            format(self.connection, self.start_stamp.isoformat(), self.address, self.rpc_id,
                   self.status, self.runtime * 1000, self.call, self.response, self.error)


class AdapterStream:
    """A wrapper that provides a synchronous interface on top of AbstractDeviceAdapter.

    DeviceAdapters have a more generic interface that is not restricted to
    exclusive use in an online fashion by a single user at a time.  This class
    implements a simpler interface on top of an AbstractDeviceAdapter that is
    easier to use from programs that only talk to a single device at a time or
    only have a single user interacting at a time.

    AdapterStream is the internal implementation that powers :class:`HardwareManager`
    and has a very similar interface.  In constrast to a DeviceAdapter which is
    command and even driven and stores very little data for a given device, AdapterStream
    contains queues that buffer reports, traces and broadcasts received from devices
    in order to make it more convenient to process them.  It also contains a generic
    RPC logging mechanism to produce a record of what RPCs were sent to a device.

    Args:
        adapter (AbstractDeviceAdapter): the DeviceAdapter that we should use
        record (string): The path to a file that we should use to record any RPCs
            sent for tracing purposes.
    """

    def __init__(self, adapter, record=None, loop=SharedLoop):
        self._scanned_devices = {}
        self._scan_lock = threading.Lock()
        self._reports = None
        self._broadcast_reports = None
        self._traces = None

        self._loop = loop
        self._record = record
        if self._record is not None:
            self._recording = []

        self._on_progress = None

        self._logger = logging.getLogger(__name__)

        self.connection_interrupted = False
        self.connected = False
        self.connection_string = None

        if isinstance(adapter, DeviceAdapter):
            adapter = AsynchronousModernWrapper(adapter)
        elif not isinstance(adapter, AbstractDeviceAdapter):
            raise ArgumentError("Unknown class passed as DeviceAdapter: %s" % str(adapter), adapter=adapter)

        self.adapter = adapter
        self._loop.run_coroutine(adapter.start())

        self.adapter.register_monitor([None], ['report', 'trace', 'broadcast', 'disconnection', 'device_seen', 'progress'],
                                      self._on_notification)

        self._start_time = monotonic()

    def scan(self, wait=None):
        """Return the devices that have been found for this device adapter.

        If the adapter indicates that we need to explicitly tell it to probe for devices, probe now.
        By default we return the list of seen devices immediately, however there are two cases where
        we will sleep here for a fixed period of time to let devices show up in our result list:

        - If we are probing then we wait for 'minimum_scan_time'
        - If we are told an explicit wait time that overrides everything and we wait that long
        """

        min_scan = self.adapter.get_config('minimum_scan_time', 0.0)
        probe_required = self.adapter.get_config('probe_required', False)

        # Figure out how long and if we need to wait before returning our scan results
        wait_time = None
        elapsed = monotonic() - self._start_time
        if elapsed < min_scan:
            wait_time = min_scan - elapsed

        # If we need to probe for devices rather than letting them just bubble up, start the probe
        # and then use our min_scan_time to wait for them to arrive via the normal _on_scan event
        if probe_required:
            self._loop.run_coroutine(self.adapter.probe())
            wait_time = min_scan

        # If an explicit wait is specified that overrides everything else
        if wait is not None:
            wait_time = wait

        if wait_time is not None:
            sleep(wait_time)

        to_remove = set()

        now = monotonic()

        with self._scan_lock:
            for name, value in self._scanned_devices.items():
                if value['expiration_time'] < now:
                    to_remove.add(name)

            for name in to_remove:
                del self._scanned_devices[name]

            devices = sorted(self._scanned_devices.values(), key=lambda x: x['uuid'])

        return devices

    def connect(self, uuid_value, wait=None):
        """Connect to a specific device by its uuid

        Attempt to connect to a device that we have previously scanned using its UUID.
        If wait is not None, then it is used in the same was a scan(wait) to override
        default wait times with an explicit value.

        Args:
            uuid_value (int): The unique id of the device that we would like to connect to.
            wait (float): Optional amount of time to force the device adapter to wait before
                attempting to connect.
        """

        if self.connected:
            raise HardwareError("Cannot connect when we are already connected")

        if uuid_value not in self._scanned_devices:
            self.scan(wait=wait)

        with self._scan_lock:
            if uuid_value not in self._scanned_devices:
                raise HardwareError("Could not find device to connect to by UUID", uuid=uuid_value)

            connstring = self._scanned_devices[uuid_value]['connection_string']

        self.connect_direct(connstring)

    def connect_direct(self, connection_string, no_rpc=False, force=False):
        """Directly connect to a device using its stream specific connection string.

        Normally, all connections to a device include opening the RPC
        interface to send RPCs.  However, there are certain, very specific,
        circumstances when you would not want to or be able to open the RPC
        interface (such as when you are using the debug interface on a bare
        MCU that has not been programmed yet).  In those cases you can pass
        no_rpc=True to not attempt to open the RPC interface.  If you do not
        open the RPC interface at connection time, there is no public
        interface to open it later, so you must disconnect and reconnect to
        the device in order to open the interface.

        Args:
            connection_string (str): The connection string that identifies the desired device.
            no_rpc (bool): Do not open the RPC interface on the device (default=False).
            force (bool): Whether to force another connection even if we think we are currently
                connected.  This is for internal use and not designed to be set externally.
        """

        if not force and self.connected:
            raise HardwareError("Cannot connect when we are already connected to '%s'" % self.connection_string)

        self._loop.run_coroutine(self.adapter.connect(0, connection_string))

        try:
            if no_rpc:
                self._logger.info("Not opening RPC interface on device %s", self.connection_string)
            else:
                self._loop.run_coroutine(self.adapter.open_interface(0, 'rpc'))
        except HardwareError as exc:
            self._logger.exception("Error opening RPC interface on device %s", connection_string)
            self._loop.run_coroutine(self.adapter.disconnect(0))
            raise exc
        except Exception as exc:
            self._logger.exception("Error opening RPC interface on device %s", connection_string)
            self._loop.run_coroutine(self.adapter.disconnect(0))
            raise HardwareError("Could not open RPC interface on device due to an exception: %s" % str(exc)) from exc

        self.connected = True
        self.connection_string = connection_string
        self.connection_interrupted = False

    def disconnect(self):
        """Disconnect from the device that we are currently connected to."""

        if not self.connected:
            raise HardwareError("Cannot disconnect when we are not connected")

        # Close the streaming and tracing interfaces when we disconnect
        self._reports = None
        self._traces = None

        self._loop.run_coroutine(self.adapter.disconnect(0))
        self.connected = False
        self.connection_interrupted = False
        self.connection_string = None

    def _try_reconnect(self):
        """Try to recover an interrupted connection."""

        try:
            if self.connection_interrupted:
                self.connect_direct(self.connection_string, force=True)
                self.connection_interrupted = False
                self.connected = True

                # Reenable streaming interface if that was open before as well
                if self._reports is not None:
                    self._loop.run_coroutine(self.adapter.open_interface(0, 'streaming'))

                # Reenable tracing interface if that was open before as well
                if self._traces is not None:
                    self._loop.run_coroutine(self.adapter.open_interface(0, 'tracing'))
        except HardwareError as exc:
            self._logger.exception("Error reconnecting to device after an unexpected disconnect")
            raise HardwareError("Device disconnected unexpectedly and we could not reconnect", reconnect_error=exc) from exc

    def send_rpc(self, address, rpc_id, call_payload, timeout=3.0):
        """Send an rpc to our connected device.

        The device must already be connected and the rpc interface open.  This
        method will synchronously send an RPC and wait for the response.  Any
        RPC errors will be raised as exceptions and if there were no errors, the
        RPC's response payload will be returned as a binary bytearray.

        See :meth:`AbstractDeviceAdapter.send_rpc` for documentation of the possible
        exceptions that can be raised here.

        Args:
            address (int): The tile address containing the RPC
            rpc_id (int): The ID of the RPC that we wish to call.
            call_payload (bytes): The payload containing encoded arguments for the
                RPC.
            timeout (float): The maximum number of seconds to wait for the RPC to
                finish.  Defaults to 3s.

        Returns:
            bytearray: The RPC's response payload.
        """

        if not self.connected:
            raise HardwareError("Cannot send an RPC if we are not in a connected state")

        if timeout is None:
            timeout = 3.0

        status = -1
        payload = b''
        recording = None

        if self.connection_interrupted:
            self._try_reconnect()

        if self._record is not None:
            recording = _RecordedRPC(self.connection_string, address, rpc_id, call_payload)
            recording.start()

        try:
            payload = self._loop.run_coroutine(self.adapter.send_rpc(0, address, rpc_id, call_payload, timeout))
            status, payload = pack_rpc_response(payload, None)
        except VALID_RPC_EXCEPTIONS as exc:
            status, payload = pack_rpc_response(payload, exc)

        if self._record is not None:
            recording.finish(status, payload)
            self._recording.append(recording)

        if self.connection_interrupted:
            self._try_reconnect()

        return unpack_rpc_response(status, payload, rpc_id, address)

    def send_highspeed(self, data, progress_callback):
        """Send a script to a device at highspeed, reporting progress.

        This method takes a binary blob and downloads it to the device as fast
        as possible, calling the passed progress_callback periodically with
        updates on how far it has gotten.

        Args:
            data (bytes): The binary blob that should be sent to the device at highspeed.
            progress_callback (callable): A function that will be called periodically to
                report progress.  The signature must be callback(done_count, total_count)
                where done_count and total_count will be passed as integers.
        """

        if not self.connected:
            raise HardwareError("Cannot send a script if we are not in a connected state")

        if isinstance(data, str) and not isinstance(data, bytes):
            raise ArgumentError("You must send bytes or bytearray to _send_highspeed", type=type(data))

        if not isinstance(data, bytes):
            data = bytes(data)

        try:
            self._on_progress = progress_callback
            self._loop.run_coroutine(self.adapter.send_script(0, data))
        finally:
            self._on_progress = None

    def enable_streaming(self):
        """Open the streaming interface and accumute reports in a queue.

        This method is safe to call multiple times in a single device
        connection. There is no way to check if the streaming interface is
        opened or to close it once it is opened (apart from disconnecting from
        the device).

        The first time this method is called, it will open the streaming
        interface and return a queue that will be filled asynchronously with
        reports as they are received.  Subsequent calls will just empty the
        queue and return the same queue without interacting with the device at
        all.

        Returns:
            queue.Queue: A queue that will be filled with reports from the device.
        """

        if not self.connected:
            raise HardwareError("Cannot enable streaming if we are not in a connected state")

        if self._reports is not None:
            _clear_queue(self._reports)
            return self._reports

        self._reports = queue.Queue()
        self._loop.run_coroutine(self.adapter.open_interface(0, 'streaming'))

        return self._reports

    def enable_tracing(self):
        """Open the tracing interface and accumulate traces in a queue.

        This method is safe to call multiple times in a single device
        connection. There is no way to check if the tracing interface is
        opened or to close it once it is opened (apart from disconnecting from
        the device).

        The first time this method is called, it will open the tracing
        interface and return a queue that will be filled asynchronously with
        reports as they are received.  Subsequent calls will just empty the
        queue and return the same queue without interacting with the device at
        all.

        Returns:
            queue.Queue: A queue that will be filled with trace data from the device.

            The trace data will be in disjoint bytes objects in the queue
        """

        if not self.connected:
            raise HardwareError("Cannot enable tracing if we are not in a connected state")

        if self._traces is not None:
            _clear_queue(self._traces)
            return self._traces

        self._traces = queue.Queue()
        self._loop.run_coroutine(self.adapter.open_interface(0, 'tracing'))

        return self._traces

    def enable_broadcasting(self):
        """Begin accumulating broadcast reports received from all devices.

        This method will allocate a queue to receive broadcast reports that
        will be filled asynchronously as broadcast reports are received.

        Returns:
            queue.Queue: A queue that will be filled with braodcast reports.
        """

        if self._broadcast_reports is not None:
            _clear_queue(self._broadcast_reports)
            return self._broadcast_reports

        self._broadcast_reports = queue.Queue()
        return self._broadcast_reports

    def enable_debug(self):
        """Open the debug interface on the connected device."""

        if not self.connected:
            raise HardwareError("Cannot enable debug if we are not in a connected state")

        self._loop.run_coroutine(self.adapter.open_interface(0, 'debug'))

    def debug_command(self, cmd, args=None, progress_callback=None):
        """Send a debug command to the connected device.

        This generic method will send a named debug command with the given
        arguments to the connected device.  Debug commands are typically used
        for things like forcible reflashing of firmware or other, debug-style,
        operations.  Not all transport protocols support debug commands and
        the supported operations vary depeneding on the transport protocol.

        Args:
            cmd (str): The name of the debug command to send.
            args (dict): Any arguments required by the given debug command
            progress_callback (callable): A function that will be called periodically to
                report progress.  The signature must be callback(done_count, total_count)
                where done_count and total_count will be passed as integers.

        Returns:
            object: The return value of the debug command, if there is one.
        """

        if args is None:
            args = {}

        try:
            self._on_progress = progress_callback
            return self._loop.run_coroutine(self.adapter.debug(0, cmd, args))
        finally:
            self._on_progress = None

    def close(self):
        """Close this adapter stream.

        This method may only be called once in the lifetime of an
        AdapterStream and it will shutdown the underlying device adapter,
        disconnect all devices and stop all background activity.

        If this stream is configured to save a record of all RPCs, the RPCs
        will be logged to a file at this point.
        """

        try:
            self._loop.run_coroutine(self.adapter.stop())
        finally:
            self._save_recording()

    def _on_notification(self, conn_string, _conn_id, name, event):
        if name not in ('device_seen', 'broadcast') and conn_string != self.connection_string:
            return

        if name == 'report':
            self._on_report(event)
        elif name == 'broadcast':
            self._on_broadcast(event)
        elif name == 'trace':
            self._on_trace(event)
        elif name == 'device_seen':
            self._on_scan(event)
        elif name == 'disconnection':
            self._on_disconnect()
        elif name == 'progress' and self._on_progress is not None:
            self._on_progress(event.get('finished'), event.get('total'))

    def _on_broadcast(self, report):
        if self._broadcast_reports is None:
            return

        self._broadcast_reports.put(report)

    def _on_report(self, report):
        if self._reports is None:
            return

        self._reports.put(report)

    def _on_trace(self, tracing_data):
        if self._traces is None:
            return

        self._traces.put(tracing_data)

    def _on_scan(self, info):
        """Callback called when a new device is discovered on this CMDStream

        Args:
            info (dict): Information about the scanned device
        """

        device_id = info['uuid']
        expiration_time = info.get('validity_period', 60)
        infocopy = deepcopy(info)

        infocopy['expiration_time'] = monotonic() + expiration_time

        with self._scan_lock:
            self._scanned_devices[device_id] = infocopy

    def _on_disconnect(self):
        """Callback when a device is disconnected unexpectedly.

        Args:
            adapter_id (int): An ID for the adapter that was connected to the device
            connection_id (int): An ID for the connection that has become disconnected
        """

        self._logger.info("Connection to device %s was interrupted", self.connection_string)
        self.connection_interrupted = True

    def _save_recording(self):
        if not self._record:
            return

        with open(self._record, "w", encoding="utf-8") as outfile:
            outfile.write("# IOTile RPC Recording\n")
            outfile.write("# Format: 1.0\n\n")
            outfile.write("Connection,Timestamp [utc isoformat],Address,RPC ID,"
                          "Duration [ms],Status,Call,Response,Error\n")

            for recording in self._recording:
                outfile.write(recording.serialize())
                outfile.write('\n')

        self._record = None


def _clear_queue(to_clear):
    """Clear all items from a queue safely."""

    while not to_clear.empty():
        try:
            to_clear.get(False)
            to_clear.task_done()
        except queue.Empty:
            continue
