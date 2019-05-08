"""A VirtualInterface that provides access to a virtual IOTile device using a BLED112

The BLED112 must be configured to have the appropriate GATT server table.  This module
just implements the correct connections between writes to GATT table characteristics and
TileBus commands.
"""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from queue import Queue
import struct
import logging
import time
import calendar
import asyncio
import binascii
from iotile.core.exceptions import HardwareError, ArgumentError
from iotile.core.hw.transport import StandardDeviceServer
from iotile.core.utilities import SharedLoop
from iotile.core.hw.exceptions import VALID_RPC_EXCEPTIONS
from iotile.core.hw.virtual import pack_rpc_response
from .async_packet import AsyncPacketBuffer
from .bled112_cmd_co import AsyncBLED112CommandProcessor
from .tilebus import TileBusService, ArchManuID
from .utilities import open_bled112


def packet_length(header):
    """
    Find the BGAPI packet length given its header
    """

    highbits = header[0] & 0b11
    lowbits = header[1]

    return (highbits << 8) | lowbits


class BLED112Server(StandardDeviceServer):
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

    CLIENT_ID = "bled_client"
    virtual_info = {}

    def __init__(self, adapter, args=None, *, loop=SharedLoop):
        super(BLED112Server, self).__init__(adapter, args, loop=loop)

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self.init_virtual_device_info(args)

        self._serial_port = open_bled112(args.get('port'), self._logger)
        self._stream = AsyncPacketBuffer(self._serial_port, header_length=4, length_function=packet_length)

        self._commands = Queue()
        self._command_task = AsyncBLED112CommandProcessor(self._stream, self._commands, stop_check_interval=0.01, loop=loop)

        # Setup our event handlers
        self._command_task.operations.every_match(self.on_connect, command_class=3, command=0)
        self._command_task.operations.every_match(self.on_disconnect, command_class=3, command=4)
        self._command_task.operations.every_match(self.on_attribute_write, command_class=2, command=2)
        self._command_task.operations.every_match(self.on_write, command_class=2, command=0)

        self.connected = False
        self._connection_handle = 0

        # Initialize state
        self.payload_notif = False
        self.header_notif = False

        # Keep track of whether we're being asked to broadcast any readings
        # as part of our advertising data
        self._broadcast_reading = None

        self.rpc_payload = bytearray(20)
        self.rpc_header = bytearray(20)
        self.device = None

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

    async def _cleanup_old_connections(self):
        """Remove all active connections and query the maximum number of supported connections
        """

        retval = await self._command_task.future_command(['_query_systemstate'])

        for conn in retval['active_connections']:
            self._logger.info("Forcible disconnecting connection %d", conn)
            await self._command_task.future_command(['_disconnect', conn])

    async def start(self):
        """Start serving access to devices over bluetooth."""

        self._command_task.start()

        try:
            await self._cleanup_old_connections()
        except Exception:
            await self.stop()
            raise

        #FIXME: This is a temporary hack, get the actual device we are serving.
        iotile_id = next(iter(self.adapter.devices))
        self.device = self.adapter.devices[iotile_id]

        self._logger.info("Serving device 0x%04X over BLED112", iotile_id)
        await self._update_advertisement()

        self.setup_client(self.CLIENT_ID, scan=False, broadcast=True)

    async def stop(self):
        """Safely shut down this interface"""
        await self._command_task.future_command(['_set_mode', 0, 0])  # Disable advertising
        await self._cleanup_old_connections()

        self._command_task.stop()
        self._stream.stop()
        self._serial_port.close()

        await super(BLED112Server, self).stop()

    async def _update_advertisement(self):
        await self._command_task.future_command(['_set_advertising_data', 0, self._advertisement()])

        if self.virtual_info['advertising_version'] == 1:
            await self._command_task.future_command(['_set_advertising_data', 1, self._scan_response()])

        await self._command_task.future_command(['_set_mode', 0, 0])  # Disable advertising

        connectability = 2
        if self.connected:
            connectability = 0

        await self._command_task.future_command(['_set_mode', 4, connectability])

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
            flags = (0 << 1) | (0 << 2) | (1 << 3) | (1 << 4)
            uuid_list = struct.pack("<BB16s", 17, 6, TileBusService.bytes_le)
            manu = struct.pack("<BBHLH", 9, 0xFF, ArchManuID, self.device.iotile_id, flags)
            return ble_flags + uuid_list + manu

        else: #self.virtual_info['advertising_version'] == 2:
            flags = (0 << 0) | (int(self.device.connected) << 2) | (0 << 3)
            reboots = self.virtual_info['reboot_count']
            voltage = int(self.virtual_info['battery_voltage'] * 32)

            OTHER = 0  #TODO
            subsecond_cnt = 0xF #TODO

            reserved = 0
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

        if self._broadcast_reading is not None:
            reading = struct.pack("<HLLL", self._broadcast_reading.stream, self._broadcast_reading.value, self._broadcast_reading.raw_time, 0)

        name = struct.pack("<BB6s", 7, 0x09, b"IOTile")
        reserved = struct.pack("<BBB", 0, 0, 0)

        response = header + voltage + reading + name + reserved
        assert len(response) == 31

        return response

    async def on_connect(self, _message):
        self._logger.debug("Received connect event")

        self.connected = True
        await self.connect(self.CLIENT_ID, str(self.device.iotile_id))
        self._connection_handle = 0


    async def on_disconnect(self, _message):
        self._logger.debug("Received disconnect event")

        self.header_notif = False
        self.payload_notif = False
        self.connected = False

        await self.disconnect(self.CLIENT_ID, str(self.device.iotile_id))

        self._logger.debug("Reenabling advertisements after disconnection")
        await self._command_task.future_command(['_set_mode', 4, 2])

    async def on_attribute_write(self, event):
        handle, flags = struct.unpack("<HB", event.payload)
        if handle in (self.ReceiveHeaderHandle, self.ReceivePayloadHandle) and flags & 0b1:
            if handle == self.ReceiveHeaderHandle:
                self.header_notif = True
            elif handle == self.ReceivePayloadHandle:
                self.payload_notif = True

            if self.header_notif and self.payload_notif:
                self._logger.debug("Opening rpc interface")
                await self.open_interface(self.CLIENT_ID, str(self.device.iotile_id), 'rpc')
        elif handle == self.StreamingHandle:
            if flags & 0b1 and not self.device.interface_open('streaming'):
                self._logger.debug("Opening streaming interface")
                await self.open_interface(self.CLIENT_ID, str(self.device.iotile_id), 'streaming')
            elif not (flags & 0b1) and self.device.interface_open('streaming'):
                self._logger.debug("Closing streaming interface")
                await self.close_interface(self.CLIENT_ID, str(self.device.iotile_id), 'streaming')
        elif handle == self.TracingHandle:
            if flags & 0b1 and not self.device.interface_open('tracing'):
                self._logger.debug("Opening tracing interface")
                await self.open_interface(self.CLIENT_ID, str(self.device.iotile_id), 'tracing')
            elif not (flags & 0b1) and self.device.interface_open('tracing'):
                self._logger.debug("Closing tracing interface")
                await self.close_interface(self.CLIENT_ID, str(self.device.iotile_id), 'tracing')

    async def on_write(self, event):
        conn, reas, handle, offset, value_len, value = struct.unpack("<BBHHB%ds" % (len(event.payload) - 7,), event.payload)
        if handle == self.SendPayloadHandle:
            self.rpc_payload = bytearray(value)
            if len(self.rpc_payload) < 20:
                self.rpc_payload += bytearray(20 - len(self.rpc_payload))
        elif handle == self.SendHeaderHandle:
            await self._call_rpc(bytearray(value))

    async def client_event_handler(self, client_id, event_tuple, user_data):
        conn_string, event_name, event = event_tuple

        if event_name == 'report':
            self._logger.debug("Sending report %s", event)
            await self._chunk_and_notify(self.StreamingHandle, event.encode())
        elif event_name == 'trace':
            self._logger.debug("Sending tracing data %s", event)
            await self._chunk_and_notify(self.TracingHandle, event)
        elif event_name == 'broadcast':
            self._logger.debug("Updating broadcast value: %s", event.visible_readings[0])
            self._broadcast_reading = event.visible_readings[0]
            await self._update_advertisement()

    async def _call_rpc(self, header):
        """Call an RPC given a header and possibly a previously sent payload

        Args:
            header (bytearray): The RPC header we should call
        """

        length, _, cmd, feature, address = struct.unpack("<BBBBB", bytes(header))
        rpc_id = (feature << 8) | cmd

        payload = self.rpc_payload[:length]

        self._logger.debug("Calling RPC %d:%04X with hex payload '%s'", address, rpc_id, binascii.hexlify(payload).decode('utf-8'))

        exception = None
        response = None

        try:
            response = await self.send_rpc(self.CLIENT_ID, str(self.device.iotile_id), address, rpc_id, bytes(payload), timeout=30.0)
        except VALID_RPC_EXCEPTIONS as err:
            exception = err
        except Exception as err:
            self._logger.exception("Error calling RPC %d:%04X", address, rpc_id)
            exception = err

        status, response = pack_rpc_response(response, exception)
        resp_header = struct.pack("<BBBB", status, 0, 0, len(response))

        await self._send_notification(self.ReceiveHeaderHandle, resp_header)

        if len(response) > 0:
            await self._send_notification(self.ReceivePayloadHandle, response)

    async def _chunk_and_notify(self, handle, payload):
        for i in range(0, len(payload), 20):
            chunk = payload[i:i + 20]

            success = await self._send_notification(handle, chunk)
            if success is False:
                self._logger.debug("Stopping chunked notification on %d at %d/%d bytes because of failure",
                                   handle, i, len(payload))

    async def _send_notification(self, handle, payload):
        while True:
            try:
                await self._command_task.future_command(['_send_notification', handle, payload])
                return True
            except HardwareError as exc:
                code = exc.params['return_value'].get('code', 0)

                # If we're told we ran out of memory, wait and try again
                if code == 0x182:
                    await asyncio.sleep(0.02)
                elif code == 0x181:  # Invalid state, the other side likely disconnected midstream
                    self._logger.warning("Error sending RPC response due to disconnection")
                    return False
                else:
                    self._logger.exception("Unkown error sending notification")
                    return False
