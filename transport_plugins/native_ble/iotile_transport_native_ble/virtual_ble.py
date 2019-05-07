"""A VirtualInterface that provides access to a virtual IOTile device using native BLE"""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import struct
import bable_interface
import logging
import time
import binascii
from iotile.core.exceptions import ExternalError
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from .tilebus import *


class NativeBLEVirtualInterface(VirtualIOTileInterface):
    """Turn a BLE adapter into a virtual IOTile

    Args:
        args (dict): A dictionary of arguments used to configure this interface.
            Currently the only supported argument is 'port' which should be a
            valid controller id (given by `sudo hcitool dev` on Linux, X in hciX)
    """

    def __init__(self, args):
        super(NativeBLEVirtualInterface, self).__init__()

        # Create logger
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        # Create the baBLE interface to interact with BLE controllers
        self.bable = bable_interface.BaBLEInterface()

        # Get the list of BLE controllers
        self.bable.start(on_error=self._on_ble_error)
        controllers = self._find_ble_controllers()
        self.bable.stop()

        if len(controllers) == 0:
            raise ExternalError("Could not find any BLE controller connected to this computer")

        # Parse args
        port = None
        if 'port' in args:
            port = args['port']

        if port is None or port == '<auto>':
            self.controller_id = controllers[0].id
        else:
            self.controller_id = int(port)
            if not any(controller.id == self.controller_id for controller in controllers):
                raise ExternalError("Could not find a BLE controller with the given ID, controller_id=%s"
                                    .format(self.controller_id))

        if 'voltage' in args:
            self.voltage = float(args['voltage'])
        else:
            self.voltage = 3.8

        # Restart baBLE with the selected controller id to prevent conflicts if multiple controllers
        self.bable.start(on_error=self._on_ble_error, exit_on_sigint=False, controller_id=self.controller_id)
        # Register the callback function into baBLE
        self.bable.on_write_request(self._on_write_request)
        self.bable.on_connected(self._on_connected)
        self.bable.on_disconnected(self._on_disconnected)

        # Initialize state
        self.connected = False
        self._connection_handle = 0

        self.payload_notif = False
        self.header_notif = False
        self.streaming = False
        self.tracing = False

        # Keep track of whether we've launched our state machine
        # to stream or trace data so that when we find more data available
        # in process() we know not to restart the streaming/tracing process
        self._stream_sm_running = False
        self._trace_sm_running = False

        self.rpc_payload = bytearray(20)
        self.rpc_header = bytearray(20)

        try:
            self._initialize_system_sync()
        except Exception:
            self.stop_sync()
            raise

    def _find_ble_controllers(self):
        """Get a list of the available and powered BLE controllers"""
        controllers = self.bable.list_controllers()
        return [ctrl for ctrl in controllers if ctrl.powered and ctrl.low_energy]

    def _on_ble_error(self, status, message):
        """Callback function called when a BLE error, not related to a request, is received. Just log it for now."""
        self._logger.error("BLE error (status=%s, message=%s)", status, message)

    def _initialize_system_sync(self):
        """Initialize the device adapter by removing all active connections and resetting scan and advertising to have
        a clean starting state."""
        connected_devices = self.bable.list_connected_devices()
        for device in connected_devices:
            self.disconnect_sync(device.connection_handle)

        self.stop_scan()

        self.set_advertising(False)

        # Register the GATT table to send the right services and characteristics when probed (like an IOTile device)
        self.register_gatt_table()

    def start(self, device):
        """Start serving access to this VirtualIOTileDevice

        Args:
            device (VirtualIOTileDevice): The device we will be providing access to
        """

        super(NativeBLEVirtualInterface, self).start(device)
        self.set_advertising(True)

    def stop(self):
        """Safely shut down this interface
        """

        super(NativeBLEVirtualInterface, self).stop()

        self.stop_sync()

    def register_gatt_table(self):
        """Register the GATT table into baBLE."""
        services = [BLEService, TileBusService]

        characteristics = [
            NameChar,
            AppearanceChar,
            ReceiveHeaderChar,
            ReceivePayloadChar,
            SendHeaderChar,
            SendPayloadChar,
            StreamingChar,
            HighSpeedChar,
            TracingChar
        ]

        self.bable.set_gatt_table(services, characteristics)

    def stop_scan(self):
        """Stop to scan."""
        try:
            self.bable.stop_scan(sync=True)
        except bable_interface.BaBLEException:
            # If we errored our it is because we were not currently scanning
            pass

    def set_advertising(self, enabled):
        """Toggle advertising."""
        if enabled:
            self.bable.set_advertising(
                enabled=True,
                uuids=[TileBusService.uuid],
                name="V_IOTile ",
                company_id=ArchManuID,
                advertising_data=self._advertisement(),
                scan_response=self._scan_response(),
                sync=True
            )
        else:
            try:
                self.bable.set_advertising(enabled=False, sync=True)
            except bable_interface.BaBLEException:
                # If advertising is already disabled
                pass

    def _advertisement(self):
        """Create advertisement data."""
        # Flags are
        # bit 0: whether we have pending data
        # bit 1: whether we are in a low voltage state
        # bit 2: whether another user is connected
        # bit 3: whether we support robust reports
        # bit 4: whether we allow fast writes

        flags = int(self.device.pending_data) | (0 << 1) | (0 << 2) | (1 << 3) | (1 << 4)
        return struct.pack("<LH", self.device.iotile_id, flags)

    def _scan_response(self):
        """Create scan response data."""
        voltage = struct.pack("<H", int(self.voltage*256))
        reading = struct.pack("<HLLL", 0xFFFF, 0, 0, 0)

        response = voltage + reading

        return response

    def stop_sync(self):
        """Safely stop this BLED112 instance without leaving it in a weird state."""

        # Disconnect connected device
        if self.connected:
            self.disconnect_sync(self._connection_handle)

        # Disable advertising
        self.set_advertising(False)
        # Stop the baBLE interface
        self.bable.stop()

        self.actions.queue.clear()  # Clear the actions queue to prevent it to send commands to baBLE after stopped

    def disconnect_sync(self, connection_handle):
        """Synchronously disconnect from whoever has connected to us

        Args:
            connection_handle (int): The handle of the connection we wish to disconnect.
        """

        self.bable.disconnect(connection_handle=connection_handle, sync=True)

    def _on_connected(self, device):
        """Callback function called when a connected event has been received.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            device (dict): Information about the newly connected device
        """
        self._logger.debug("Device connected event: {}".format(device))

        self.connected = True
        self._connection_handle = device['connection_handle']
        self.device.connected = True

    def _on_disconnected(self, device):
        """Callback function called when a disconnected event has been received.
        This resets any open interfaces on the virtual device and clears any
        in progress traces and streams.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            device (dict): Information about the newly connected device
        """

        self._logger.debug("Device disconnected event: {}".format(device))

        if self.streaming:
            self.device.close_streaming_interface()
            self.streaming = False

        if self.tracing:
            self.device.close_tracing_interface()
            self.tracing = False

        self.device.connected = False
        self.connected = False
        self._connection_handle = 0
        self.header_notif = False
        self.payload = False

        self._clear_reports()
        self._clear_traces()

        self._defer(self.set_advertising, [True])

    def _on_write_request(self, request):
        """Callback function called when a write request has been received.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            request (dict): Information about the request
              - connection_handle (int): The connection handle that sent the request
              - attribute_handle (int): The attribute handle to write
              - value (bytes): The value to write
        """
        if request['connection_handle'] != self._connection_handle:
            return False

        attribute_handle = request['attribute_handle']

        # If write to configure notification
        config_handles = [
            ReceiveHeaderChar.config_handle,
            ReceivePayloadChar.config_handle,
            StreamingChar.config_handle,
            TracingChar.config_handle
        ]
        if attribute_handle in config_handles:
            notification_enabled, _ = struct.unpack('<BB', request['value'])

            # ReceiveHeader or ReceivePayload
            if attribute_handle in [ReceiveHeaderChar.config_handle, ReceivePayloadChar.config_handle] and notification_enabled:
                if attribute_handle == ReceiveHeaderChar.config_handle:
                    self.header_notif = True
                elif attribute_handle == ReceivePayloadChar.config_handle:
                    self.payload_notif = True

                if self.header_notif and self.payload_notif:
                    self.device.open_rpc_interface()

            # Streaming
            elif attribute_handle == StreamingChar.config_handle:
                if notification_enabled and not self.streaming:
                    self.streaming = True

                    # If we should send any reports, queue them for sending
                    reports = self.device.open_streaming_interface()
                    if reports is not None:
                        self._queue_reports(*reports)

                elif not notification_enabled and self.streaming:
                    self.streaming = False
                    self.device.close_streaming_interface()

            # Tracing
            elif attribute_handle == TracingChar.config_handle:
                if notification_enabled and not self.tracing:
                    self.tracing = True

                    # If we should send any trace data, queue it immediately
                    traces = self.device.open_tracing_interface()
                    if traces is not None:
                        self._queue_traces(*traces)

                elif not notification_enabled and self.tracing:
                    self.tracing = False
                    self.device.close_tracing_interface()

            return True
        # If write an RPC
        elif attribute_handle in [SendHeaderChar.value_handle, SendPayloadChar.value_handle]:
            # Payload
            if attribute_handle == SendPayloadChar.value_handle:
                self.rpc_payload = bytearray(request['value'])
                if len(self.rpc_payload) < 20:
                    self.rpc_payload += bytearray(20 - len(self.rpc_payload))
            # Header
            elif attribute_handle == SendHeaderChar.value_handle:
                self._defer(self._call_rpc, [bytearray(request['value'])])

            return True
        else:
            return False

    def _call_rpc(self, header):
        """Call an RPC given a header and possibly a previously sent payload
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            header (bytearray): The RPC header we should call
        """

        length, _, cmd, feature, address = struct.unpack("<BBBBB", bytes(header))
        rpc_id = (feature << 8) | cmd

        payload = self.rpc_payload[:length]

        status = (1 << 6)
        try:
            response = self.device.call_rpc(address, rpc_id, bytes(payload))
            if len(response) > 0:
                status |= (1 << 7)
        except (RPCInvalidIDError, RPCNotFoundError):
            status = 2  # FIXME: Insert the correct ID here
            response = b''
        except TileNotFoundError:
            status = 0xFF
            response = b''
        except Exception:
            status = 3
            response = b''
            self._logger.exception("Exception raise while calling rpc, header=%s, payload=%s", header, payload)

        resp_header = struct.pack("<BBBB", status, 0, 0, len(response))

        if len(response) > 0:
            self._send_rpc_response(
                (ReceiveHeaderChar.value_handle, resp_header),
                (ReceivePayloadChar.value_handle, response)
            )
        else:
            self._send_rpc_response((ReceiveHeaderChar.value_handle, resp_header))

    def _send_notification(self, handle, payload):
        """Send a notification over BLE
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            handle (int): The handle to notify on
            payload (bytearray): The value to notify
        """

        self.bable.notify(
            connection_handle=self._connection_handle,
            attribute_handle=handle,
            value=payload
        )

    def _send_rpc_response(self, *packets):
        """Send an RPC response.
        It is executed in the baBLE working thread: should not be blocking.

        The RPC response is notified in one or two packets depending on whether or not
        response data is included. If there is a temporary error sending one of the packets
        it is retried automatically. If there is a permanent error, it is logged and the response
        is abandoned.
        """

        if len(packets) == 0:
            return

        handle, payload = packets[0]

        try:
            self._send_notification(handle, payload)
        except bable_interface.BaBLEException as err:
            if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                time.sleep(0.05)
                self._defer(self._send_rpc_response, list(packets))
            else:
                self._logger.exception("Error while sending RPC response, handle=%s, payload=%s", handle, payload)

            return

        if len(packets) > 1:
            self._defer(self._send_rpc_response, list(packets[1:]))

    def _stream_data(self, chunk=None):
        """Stream reports to the ble client in 20 byte chunks

        Args:
            chunk (bytearray): A chunk that should be sent instead of requesting a
                new chunk from the pending reports.
        """

        # If we failed to transmit a chunk, we will be requeued with an argument
        self._stream_sm_running = True

        if chunk is None:
            chunk = self._next_streaming_chunk(20)

        if chunk is None or len(chunk) == 0:
            self._stream_sm_running = False
            return

        try:
            self._send_notification(StreamingChar.value_handle, chunk)
            self._defer(self._stream_data)
        except bable_interface.BaBLEException as err:
            if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                time.sleep(0.05)
                self._defer(self._stream_data, [chunk])
            else:
                self._logger.exception("Error while streaming data")

    def _send_trace(self, chunk=None):
        """Stream tracing data to the ble client in 20 byte chunks

        Args:
            chunk (bytearray): A chunk that should be sent instead of requesting a
                new chunk from the pending reports.
        """

        self._trace_sm_running = True
        # If we failed to transmit a chunk, we will be requeued with an argument
        if chunk is None:
            chunk = self._next_tracing_chunk(20)

        if chunk is None or len(chunk) == 0:
            self._trace_sm_running = False
            return

        try:
            self._send_notification(TracingChar.value_handle, chunk)
            self._defer(self._send_trace)
        except bable_interface.BaBLEException as err:
            if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                time.sleep(0.05)
                self._defer(self._send_trace, [chunk])
            else:
                self._logger.exception("Error while tracing data")

    def process(self):
        """Periodic nonblocking processes"""

        super(NativeBLEVirtualInterface, self).process()

        if (not self._stream_sm_running) and (not self.reports.empty()):
            self._stream_data()

        if (not self._trace_sm_running) and (not self.traces.empty()):
            self._send_trace()
