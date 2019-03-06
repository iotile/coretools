"""A VirtualInterface that provides access to a virtual IOTile device using a BLED112

The BLED112 must be configured to have the appropriate GATT server table.  This module
just implements the correct connections between writes to GATT table characteristics and
TileBus commands.
"""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from queue import Queue
import traceback
import struct
import logging
import time
import calendar
import binascii
from threading import Lock
import serial
import serial.tools.list_ports
from iotile.core.exceptions import ExternalError, HardwareError, ArgumentError
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.hw.reports import BroadcastReport
from .async_packet import AsyncPacketBuffer
from .bled112_cmd import BLED112CommandProcessor
from .tilebus import TileBusService, ArchManuID


def packet_length(header):
    """
    Find the BGAPI packet length given its header
    """

    highbits = header[0] & 0b11
    lowbits = header[1]

    return (highbits << 8) | lowbits


class BLED112VirtualInterface(VirtualIOTileInterface):
    """Turn a BLED112 ble adapter into a virtual IOTile

    Args:
        args (dict): A dictionary of arguments used to configure this interface.
            Currently the only supported argument is 'port' which should be a
            path to a BLED112 device file (or something like COMX on windows)
    """

    SendHeaderHandle = 8
    SendPayloadHandle = 10
    ReceiveHeaderHandle = 12
    ReceivePayloadHandle = 15
    StreamingHandle = 18
    HighspeedHandle = 21
    TracingHandle = 23

    virtual_info = {}

    def __init__(self, args):
        super(BLED112VirtualInterface, self).__init__()

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self.init_virtual_device_info(args)

        port = None
        if 'port' in args:
            port = args['port']

        if port is None or port == '<auto>':
            devices = self.find_bled112_devices()
            if len(devices) > 0:
                port = devices[0]
            else:
                raise ExternalError("Could not find any BLED112 adapters connected to this computer")

        self._serial_port = serial.Serial(port, 256000, timeout=0.01, rtscts=True, exclusive=True)
        self._stream = AsyncPacketBuffer(self._serial_port, header_length=4, length_function=packet_length)
        self._commands = Queue()
        self._command_task = BLED112CommandProcessor(self._stream, self._commands, stop_check_interval=0.01)
        self._command_task.event_handler = self._handle_event
        self._command_task.start()

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

        # Keep track of whether we're being asked to broadcast any readings
        # as part of our advertising data
        self._broadcast_reading = None
        self._broadcast_lock = Lock()

        self.rpc_payload = bytearray(20)
        self.rpc_header = bytearray(20)

        try:
            self.initialize_system_sync()
        except Exception:
            self.stop_sync()
            raise

    def init_virtual_device_info(self, args):
        self.virtual_info['advertising_version'] = int(args.get('advertising_version', '1'), 0)
        if self.virtual_info['advertising_version'] not in (1, 2):
            raise ArgumentError("Invalid advertising version specified in args",
            supported=(1, 2), found=self.virtual_info['advertising_version'])

        self.virtual_info['reboot_count'] = int(args.get('reboot_count', '1'), 0)
        if self.virtual_info['reboot_count'] <= 0:
            raise ArgumentError("Reboot count must be greater than 0.",
            supported="> 0", found=self.virtual_info['reboot_count'])

        self.virtual_info['mac_value'] = int(args.get('mac_value', '0'), 0)
        if self.virtual_info['mac_value'] < 0 or self.virtual_info['mac_value'] > 0xFFFFFFFF:
            raise ArgumentError("MAC value is limited to 32bits.",
            supported="0 - 0xFFFFFFFF", found=self.virtual_info['mac_value'])

        self.virtual_info['battery_voltage'] = float(args.get('battery_voltage',"3.14159"))
        if self.virtual_info['battery_voltage'] < 0 or self.virtual_info['battery_voltage'] > 7.9:
            raise ArgumentError("Battery voltage is invalid",
            supported="0 - 7.9", found=self.virtual_info['battery_voltage'])

    @classmethod
    def find_bled112_devices(cls):
        found_devs = []

        # Look for BLED112 dongles on this computer and start an instance on each one
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if not hasattr(p, 'pid') or not hasattr(p, 'vid'):
                continue

            # Check if the device matches the BLED112's PID/VID combination
            if p.pid == 1 and p.vid == 9304:
                found_devs.append(p.device)

        return found_devs

    def initialize_system_sync(self):
        """Remove all active connections and query the maximum number of supported connections
        """

        retval = self._command_task.sync_command(['_query_systemstate'])

        for conn in retval['active_connections']:
            self.disconnect_sync(conn)

    def start(self, device):
        """Start serving access to this VirtualIOTileDevice

        Args:
            device (VirtualIOTileDevice): The device we will be providing access to
        """
        super(BLED112VirtualInterface, self).start(device)

        self._command_task.sync_command(['_set_advertising_data', 0, self._advertisement()])

        if self.virtual_info['advertising_version'] == 1:
            self._command_task.sync_command(['_set_advertising_data', 1, self._scan_response()])

        self._command_task.sync_command(['_set_mode', 0, 0])  # Disable advertising
        self._command_task.sync_command(['_set_mode', 4, 2])  # Enable undirected connectable

    def stop(self):
        """Safely shut down this interface
        """
        super(BLED112VirtualInterface, self).stop()

        self._command_task.sync_command(['_set_mode', 0, 0])  # Disable advertising
        self.stop_sync()

    def process(self):
        """Periodic nonblocking processes
        """
        super(BLED112VirtualInterface, self).process()

        if (not self._stream_sm_running) and (not self.reports.empty()):
            self._stream_data()

        if (not self._trace_sm_running) and (not self.traces.empty()):
            self._send_trace()

    def _queue_reports(self, *reports):
        """Queue reports for transmission over the streaming interface.

        The primary reason for this function is to allow for a single implementation
        of encoding and chunking reports for streaming.

        We override the function to inspect whether the user is putting a broadcast
        report and if so, we handle it specially

        Args:
            *reports (list): A list of IOTileReport objects that should be sent over
                the streaming interface. If you want to get a callback when the report
                actually finishes being streamed out over the interface, you can put
                a tuple of (IOTileReport, callback) instead of an IOTileReport.

                Your callback, if supplied will be called when the report
                finishes being streamed.
        """

        for report, callback  in reports:
            if isinstance(report, BroadcastReport):
                with self._broadcast_lock:
                    self._broadcast_reading = report.visible_readings[0]

                if self.device:
                    if self.virtual_info['advertising_version'] == 1:
                        self._defer(self._command_task.sync_command, [['_set_advertising_data', 1, self._scan_response()]])
                    else:
                        self._defer(self._command_task.sync_command, [['_set_advertising_data', 0, self._advertisement()]])

                if callback is not None:
                    callback(True)

                continue

            self.reports.put((report, callback))

    def _advertisement(self):
        # Flags for version 1 are:
        #   bit 0: whether we have pending data
        #   bit 1: whether we are in a low voltage state
        #   bit 2: whether another user is connected
        #   bit 3: whether we support robust reports
        #   bit 4: whether we allow fast writes
        # Flags for version 2 are:
        #   bit 0: User is connected
        #   bit 1: POD has data to stream
        #   bit 2: Broadcast data is encrypted and authenticated using AES-128 CCM
        #   bit 3: Broadcast key is device key (otherwise user key)
        #   bit 4-7: Reserved

        ble_flags = struct.pack("<BBB", 2, 1, 0x4 | 0x2)  # General discoverability and no BR/EDR support

        if self.virtual_info['advertising_version'] == 1:
            flags = (0 << 1) | (0 << 2) | (1 << 3) | (1 << 4) | (int(self.device.pending_data))
            uuid_list = struct.pack("<BB16s", 17, 6, TileBusService.bytes_le)
            manu = struct.pack("<BBHLH", 9, 0xFF, ArchManuID, self.device.iotile_id, flags)
            return ble_flags + uuid_list + manu

        else: #self.virtual_info['advertising_version'] == 2:
            flags = (0 << 0) | (int(self.device.pending_data) << 1) | (int(self.device.connected) << 2) | (0 << 3)
            reboots = self.virtual_info['reboot_count']
            voltage = int(self.virtual_info['battery_voltage'] * 32)

            OTHER = 0  #TODO
            subsecond_cnt = 0xF #TODO

            reserved = 0
            with self._broadcast_lock:
                timestamp = calendar.timegm(time.gmtime())
                if self._broadcast_reading is not None:
                    bcast_stream = self._broadcast_reading.stream
                    bcast_value = self._broadcast_reading.value
                else:
                    bcast_stream = 0xFFFF
                    bcast_value = 0xFFFFFFFF

            mac = self.virtual_info['mac_value']  #TODO: Calculate MAC

            reboots_hi = (reboots & 0xFF0000) >> 16
            reboots_lo = (reboots & 0x00FFFF)

            data1 = struct.pack("<BBHL", 27, 0x16, 0x03C0, self.device.iotile_id)
            data2 = struct.pack("<HBBLBB", reboots_lo, reboots_hi, flags, timestamp, voltage, OTHER)
            data3 = struct.pack("<HLL", bcast_stream, bcast_value, mac)

            return ble_flags + data1 + data2 + data3

    def _scan_response(self):
        if self.virtual_info['advertising_version'] != 1:
            raise ArgumentError("Invalid advertising version for scan response.", supported=1, found=self.virtual_info['advertising_version'])

        header = struct.pack("<BBH", 19, 0xFF, ArchManuID)
        voltage = struct.pack("<H", int(3.8*256))  # FIXME: Hardcoded 3.8V voltage perhaps supply in json file

        reading = struct.pack("<HLLL", 0xFFFF, 0, 0, 0)

        with self._broadcast_lock:
            if self._broadcast_reading is not None:
                reading = struct.pack("<HLLL", self._broadcast_reading.stream, self._broadcast_reading.value, self._broadcast_reading.raw_time, 0)

        name = struct.pack("<BB6s", 7, 0x09, b"IOTile")
        reserved = struct.pack("<BBB", 0, 0, 0)

        response = header + voltage + reading + name + reserved
        assert len(response) == 31

        return response

    def stop_sync(self):
        """Safely stop this BLED112 instance without leaving it in a weird state

        """

        if self.connected:
            self.disconnect_sync(self._connection_handle)

        self._command_task.stop()
        self._stream.stop()
        self._serial_port.close()

    def disconnect_sync(self, connection_handle):
        """Synchronously disconnect from whoever has connected to us

        Args:
            connection_handle (int): The handle of the connection we wish to disconnect.
        """

        self._command_task.sync_command(['_disconnect', connection_handle])

    def _on_disconnect(self):
        """Clean up after a client disconnects

        This resets any open interfaces on the virtual device and clears any
        in progress traces and streams.  This function is called in the
        main event loop after the client has already disconnected, so it should
        not attempt to interact with the bluetooth stack in any way.
        """

        if self.streaming:
            self.device.close_streaming_interface()
            self.streaming = False

        if self.tracing:
            self.device.close_tracing_interface()
            self.tracing = False

        self.device.connected = False

        self._clear_reports()
        self._clear_traces()

    def _handle_event(self, event):
        self._logger.debug("BLED Event: {}".format(str(event)))

        #Check if we're being connected to
        if event.command_class == 3 and event.command == 0:
            self.connected = True
            self._connection_handle = 0
            self.device.connected = True
            self._audit('ClientConnected')

        # Check if we're being disconnected from
        elif event.command_class == 3 and event.command == 4:
            self.connected = False
            self._connection_handle = 0
            self.header_notif = False
            self.payload = False

            # Reenable advertising and clean up the virtual device on disconnection
            self._defer(self._on_disconnect)
            self._defer(self._command_task.sync_command, [['_set_mode', 4, 2]])
            self._audit('ClientDisconnected')

        #Check for attribute writes that indicate interfaces being opened or closed
        elif event.command_class == 2 and event.command == 2:
            handle, flags = struct.unpack("<HB", event.payload)
            if (handle == self.ReceiveHeaderHandle or handle == self.ReceivePayloadHandle) and flags & 0b1:
                if handle == self.ReceiveHeaderHandle:
                    self.header_notif = True
                elif handle == self.ReceivePayloadHandle:
                    self.payload_notif = True

                if self.header_notif and self.payload_notif:
                    self.device.open_rpc_interface()
                    self._audit("RPCInterfaceOpened")
            elif handle == self.StreamingHandle:
                if flags & 0b1 and not self.streaming:
                    self.streaming = True

                    # If we should send any reports, queue them for sending
                    reports = self.device.open_streaming_interface()
                    if reports is not None:
                        self._queue_reports(*reports)

                    self._audit('StreamingInterfaceOpened')
                elif not (flags & 0b1) and self.streaming:
                    self.streaming = False
                    self.device.close_streaming_interface()
                    self._audit('StreamingInterfaceClosed')
            elif handle == self.TracingHandle:
                if flags & 0b1 and not self.tracing:
                    self.tracing = True

                    # If we should send any trace data, queue it immediately
                    traces = self.device.open_tracing_interface()
                    if traces is not None:
                        self._queue_traces(*traces)

                    self._audit('TracingInterfaceOpened')
                elif not (flags & 0b1) and self.tracing:
                    self.tracing = False
                    self.device.close_tracing_interface()
                    self._audit('TracingInterfaceClosed')

        # Now check for RPC writes
        elif event.command_class == 2 and event.command == 0:
            conn, reas, handle, offset, value_len, value = struct.unpack("<BBHHB%ds" % (len(event.payload) - 7,), event.payload)
            if handle == self.SendPayloadHandle:
                self.rpc_payload = bytearray(value)
                if len(self.rpc_payload) < 20:
                    self.rpc_payload += bytearray(20 - len(self.rpc_payload))
            elif handle == self.SendHeaderHandle:
                self._defer(self._call_rpc, [bytearray(value)])

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
            response = b""
        except TileNotFoundError:
            status = 0xFF
            response = b""
        except Exception:
            #Don't allow exceptions in second thread or we will deadlock on closure
            status = 3
            response = b""

            print("*** EXCEPTION OCCURRED IN RPC ***")
            traceback.print_exc()
            print("*** END EXCEPTION ***")

        self._audit("RPCReceived", rpc_id=rpc_id, address=address, payload=binascii.hexlify(payload), status=status, response=binascii.hexlify(response))

        resp_header = struct.pack("<BBBB", status, 0, 0, len(response))

        if len(response) > 0:
            self._defer(self._send_rpc_response, [(self.ReceiveHeaderHandle, resp_header), (self.ReceivePayloadHandle, response)])
        else:
            self._defer(self._send_rpc_response, [(self.ReceiveHeaderHandle, resp_header)])

    def _send_rpc_response(self, *packets):
        """Send an RPC response.

        The RPC response is notified in one or two packets depending on whether or not
        response data is included.  If there is a temporary error sending one of the packets
        it is retried automatically.  If there is a permanent error, it is logged and the response
        is abandoned.  This is important because otherwise we can have issues where an RPC
        response that is sent to a client that disconnected immediately after requesting the RPC
        can cause the virtual_interface to crash.
        """

        if len(packets) == 0:
            return

        handle, payload = packets[0]

        try:
            self._command_task.sync_command(['_send_notification', handle, payload])
        except HardwareError as exc:
            code = exc.params['return_value'].get('code', 0)

            # If we're told we ran out of memory, wait and try again
            if code == 0x182:
                time.sleep(.02)
                self._defer(self._send_rpc_response, packets)
            elif code == 0x181:  # Invalid state, the other side likely disconnected midstream
                self._audit('ErrorSendingRPCResponse')
            else:
                print("*** EXCEPTION OCCURRED RESPONDING TO RPC ***")
                traceback.print_exc()
                print("*** END EXCEPTION ***")

            return

        if len(packets) > 1:
            self._defer(self._send_rpc_response, packets[1:])

    def _send_notification(self, handle, payload):
        """Send a notification over BLE

        Args:
            handle (int): The handle to notify on
            payload (bytearray): The value to notify
        """

        self._command_task.sync_command(['_send_notification', handle, payload])

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
            self._send_notification(self.StreamingHandle, chunk)
            self._defer(self._stream_data)
        except HardwareError as exc:
            retval = exc.params['return_value']

            # If we're told we ran out of memory, wait and try again
            if retval.get('code', 0) == 0x182:
                time.sleep(.02)
                self._defer(self._stream_data, [chunk])
            elif retval.get('code', 0) == 0x181:  # Invalid state, the other side likely disconnected midstream
                self._audit('ErrorStreamingReport')  # If there was an error, stop streaming but don't choke
            else:
                print("*** EXCEPTION OCCURRED STREAMING DATA ***")
                traceback.print_exc()
                print("*** END EXCEPTION ***")
                self._audit('ErrorStreamingReport')  # If there was an error, stop streaming but don't choke

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
            self._send_notification(self.TracingHandle, chunk)
            self._defer(self._send_trace)
        except HardwareError as exc:
            retval = exc.params['return_value']

            # If we're told we ran out of memory, wait and try again
            if retval.get('code', 0) == 0x182:
                time.sleep(.02)
                self._defer(self._send_trace, [chunk])
            elif retval.get('code', 0) == 0x181:  # Invalid state, the other side likely disconnected midstream
                self._audit('ErrorStreamingTrace')  # If there was an error, stop streaming but don't choke
            else:
                print("*** EXCEPTION OCCURRED STREAMING DATA ***")
                traceback.print_exc()
                print("*** END EXCEPTION ***")
                self._audit('ErrorStreamingTrace')  # If there was an error, stop streaming but don't choke
