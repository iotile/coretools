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

        self.bable = bable_interface.BaBLEInterface()

        port = None
        if 'port' in args:
            port = args['port']

        if port is None or port == '<auto>':
            self.bable.start(on_error=self._on_ble_error)
            controllers = self.find_ble_controllers()
            self.bable.stop()

            if len(controllers) > 0:
                self.controller_id = controllers[0].id
            else:
                raise ExternalError("Could not find any BLE controller connected to this computer")
        else:
            self.controller_id = int(port)

        if 'voltage' in args:
            self.voltage = float(args['voltage'])
        else:
            self.voltage = 3.8

        self._logger = logging.getLogger(__name__)
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d %(levelname).3s [%(name)s] %(message)s', '%y-%m-%d %H:%M:%S'))
        self._logger.addHandler(console)
        self._logger.setLevel(logging.DEBUG)
        # self._logger.addHandler(logging.NullHandler())

        self.bable.start(on_error=self._on_ble_error, exit_on_sigint=False, controller_id=self.controller_id)
        self.bable.on_write_request(self._on_write_request)
        self.bable.on_connected(self._on_connected)
        self.bable.on_disconnected(self._on_disconnected)

        self.connected = False
        self._connection_handle = 0

        # Initialize state
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
            self.initialize_system_sync()
        except Exception:
            self.stop_sync()
            raise

    def find_ble_controllers(self):
        controllers = self.bable.list_controllers()
        return [ctrl for ctrl in controllers if ctrl.powered and ctrl.low_energy]

    def _on_ble_error(self, status, message):
        self._logger.error("BLE error (status=%s, message=%s)", status, message)

    def initialize_system_sync(self):
        connected_devices = self.bable.list_connected_devices()
        for device in connected_devices:
            self.disconnect_sync(device.connection_handle)

        # If the dongle was previously left in a dirty state while still scanning, it will
        # not allow new scans to be started. So, forcibly stop any in progress scans.
        # This throws a hardware error if scanning is not in progress which should be ignored.
        self.stop_scan()

        self.set_advertising(False)

        self.register_gatt_table()

    def register_gatt_table(self):
        services = [
            bable_interface.Service(uuid='1800', handle=0x0001, group_end_handle=0x0005),
            bable_interface.Service(uuid=TileBusService, handle=0x000B, group_end_handle=0xFFFF)
        ]

        characteristics = [
            bable_interface.Characteristic(uuid='2a00', handle=0x0002, value_handle=0x0003, const_value=b'V_IOTile ', read=True),
            bable_interface.Characteristic(uuid='2a01', handle=0x0004, value_handle=0x0005, const_value=b'\x80\x00', read=True),
            bable_interface.Characteristic(uuid=TileBusReceiveHeaderCharacteristic, handle=0x000C, value_handle=0x000D, config_handle=0x000E, notify=True),
            bable_interface.Characteristic(uuid=TileBusReceivePayloadCharacteristic, handle=0x000F, value_handle=0x0010, config_handle=0x0011, notify=True),
            bable_interface.Characteristic(uuid=TileBusSendHeaderCharacteristic, handle=0x0012, value_handle=0x0013, write=True),
            bable_interface.Characteristic(uuid=TileBusSendPayloadCharacteristic, handle=0x0014, value_handle=0x0015, write=True),
            bable_interface.Characteristic(uuid=TileBusStreamingCharacteristic, handle=0x0016, value_handle=0x0017, config_handle=0x0018, notify=True),
            bable_interface.Characteristic(uuid=TileBusHighSpeedCharacteristic, handle=0x0019, value_handle=0x001A, write=True),
            bable_interface.Characteristic(uuid=TileBusTracingCharacteristic, handle=0x001B, value_handle=0x001C, config_handle=0x001D, notify=True)
        ]

        self.bable.set_gatt_table(services, characteristics)

    def stop_scan(self):
        try:
            self.bable.stop_scan(sync=True)
        except bable_interface.BaBLEException:
            # If we errored our it is because we were not currently scanning, so make sure
            # we update our self.scanning flag (which would not be updated by stop_scan since
            # it raised an exception.)
            pass

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

    def set_advertising(self, enabled):
        if enabled:
            self.bable.set_advertising(
                enabled=True,
                uuids=[TileBusService],
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

    def process(self):
        """Periodic nonblocking processes"""

        super(NativeBLEVirtualInterface, self).process()

        if (not self._stream_sm_running) and (not self.reports.empty()):
            self._stream_data()

        if (not self._trace_sm_running) and (not self.traces.empty()):
            self._send_trace()

    def _advertisement(self):
        # Flags are
        # bit 0: whether we have pending data
        # bit 1: whether we are in a low voltage state
        # bit 2: whether another user is connected
        # bit 3: whether we support robust reports
        # bit 4: whether we allow fast writes

        flags = int(self.device.pending_data) | (0 << 1) | (0 << 2) | (1 << 3) | (1 << 4)
        return struct.pack("<LH", self.device.iotile_id, flags)

    def _scan_response(self):
        voltage = struct.pack("<H", int(self.voltage*256))
        reading = struct.pack("<HLLL", 0xFFFF, 0, 0, 0)

        response = voltage + reading

        return response

    def stop_sync(self):
        """Safely stop this BLED112 instance without leaving it in a weird state"""

        if self.connected:
            self.disconnect_sync(self._connection_handle)

        self.set_advertising(False)
        self.bable.stop()

    def disconnect_sync(self, connection_handle):
        """Synchronously disconnect from whoever has connected to us

        Args:
            connection_handle (int): The handle of the connection we wish to disconnect.
        """

        self.bable.disconnect(connection_handle=connection_handle, sync=True)

    def _on_connected(self, device):
        self._logger.debug("Device connected event: {}".format(device))

        self.connected = True
        self._connection_handle = device['connection_handle']
        self.device.connected = True
        self._audit('ClientConnected')

    def _on_disconnected(self, device):
        """Clean up after a client disconnects

        This resets any open interfaces on the virtual device and clears any
        in progress traces and streams.
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
        self._audit('ClientDisconnected')

    def _on_write_request(self, request):
        if request['controller_id'] != self.controller_id or request['connection_handle'] != self._connection_handle:
            return False

        attribute_handle = request['attribute_handle']

        # If write to configure notification
        if attribute_handle in [0x000E, 0x0011, 0x0018, 0x001D]:
            notification_enabled, _ = struct.unpack('<BB', request['value'])

            # ReceiveHeader or ReceivePayload
            if attribute_handle == 0x000E or attribute_handle == 0x0011 and notification_enabled:
                if attribute_handle == 0x000E:
                    self.header_notif = True
                elif attribute_handle == 0x0011:
                    self.payload_notif = True

                if self.header_notif and self.payload_notif:
                    self.device.open_rpc_interface()
                    self._audit("RPCInterfaceOpened")

            # Streaming
            elif attribute_handle == 0x0018:
                if notification_enabled and not self.streaming:
                    self.streaming = True

                    # If we should send any reports, queue them for sending
                    reports = self.device.open_streaming_interface()
                    if reports is not None:
                        self._queue_reports(*reports)

                    self._audit('StreamingInterfaceOpened')
                elif not notification_enabled and self.streaming:
                    self.streaming = False
                    self.device.close_streaming_interface()
                    self._audit('StreamingInterfaceClosed')

            # Tracing
            elif attribute_handle == 0x001D:
                if notification_enabled and not self.tracing:
                    self.tracing = True

                    # If we should send any trace data, queue it immediately
                    traces = self.device.open_tracing_interface()
                    if traces is not None:
                        self._queue_traces(*traces)

                    self._audit('TracingInterfaceOpened')
                elif not notification_enabled and self.tracing:
                    self.tracing = False
                    self.device.close_tracing_interface()
                    self._audit('TracingInterfaceClosed')

            return True
        # If write an RPC
        elif attribute_handle in [0x0013, 0x0015]:
            # Payload
            if attribute_handle == 0x0015:
                self.rpc_payload = bytearray(request['value'])
                if len(self.rpc_payload) < 20:
                    self.rpc_payload += bytearray(20 - len(self.rpc_payload))
            # Header
            elif attribute_handle == 0x0013:
                self._defer(self._call_rpc, [bytearray(request['value'])])

            return True
        else:
            return False

    def _call_rpc(self, header):
        """Call an RPC given a header and possibly a previously sent payload

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

        self._audit(
            "RPCReceived",
            rpc_id=rpc_id,
            address=address,
            payload=binascii.hexlify(payload),
            status=status,
            response=binascii.hexlify(response)
        )

        resp_header = struct.pack("<BBBB", status, 0, 0, len(response))

        if len(response) > 0:
            self._send_rpc_response((0x000D, resp_header), (0x0010, response))
        else:
            self._send_rpc_response((0x000D, resp_header))

    def _send_rpc_response(self, *packets):
        """Send an RPC response.

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
                self._audit('ErrorSendingRPCResponse')
                self._logger.exception("Error while sending RPC response, handle=%s, payload=%s", handle, payload)

            return

        if len(packets) > 1:
            self._defer(self._send_rpc_response, list(packets[1:]))

    def _send_notification(self, handle, payload):
        """Send a notification over BLE

        Args:
            handle (int): The handle to notify on
            payload (bytearray): The value to notify
        """

        # TODO: modify notify to take a Characteristic instead of attribute_handle + register characteristics in variablesZ
        self.bable.notify(
            connection_handle=self._connection_handle,
            attribute_handle=handle,
            value=payload
        )

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
            self._send_notification(0x0017, chunk)
            self._defer(self._stream_data)
        except bable_interface.BaBLEException as err:
            if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                time.sleep(0.05)
                self._defer(self._stream_data, [chunk])
            else:
                self._audit('ErrorStreamingReport')  # If there was an error, stop streaming but don't choke
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
            self._send_notification(0x001C, chunk)
            self._defer(self._send_trace)
        except bable_interface.BaBLEException as err:
            if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                time.sleep(0.05)
                self._defer(self._send_trace, [chunk])
            else:
                self._audit('ErrorStreamingTrace')  # If there was an error, stop streaming but don't choke
                self._logger.exception("Error while tracing data")
