"""A VirtualInterface that provides access to a virtual IOTile device using a BLED112

The BLED112 must be configured to have the appropriate GATT server table.  This module
just implements the correct connections between writes to GATT table characteristics and
TileBus commands. 
"""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from Queue import Queue
import time
import struct
import threading
import logging
import datetime
import uuid
import copy
import serial
import serial.tools.list_ports
from iotile.core.exceptions import EnvironmentError
from iotile.core.utilities.packed import unpack
from iotile.core.hw.reports.parser import IOTileReportParser
from async_packet import AsyncPacketBuffer
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from bled112_cmd import BLED112CommandProcessor
from tilebus import *
import bgapi_structures

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

    def __init__(self, args):
        super(BLED112VirtualInterface, self).__init__()

        port = None
        if 'port' in args:
            port = args['port']

        if port is None or port == '<auto>':
            devices = self.find_bled112_devices()
            if len(devices) > 0:
                port = devices[0]
            else:
                raise EnvironmentError("Could not find any BLED112 adapters connected to this computer")

        self._serial_port = serial.Serial(port, 256000, timeout=0.01, rtscts=True)
        self._stream = AsyncPacketBuffer(self._serial_port, header_length=4, length_function=packet_length)
        self._commands = Queue()
        self._command_task = BLED112CommandProcessor(self._stream, self._commands)
        self._command_task.event_handler = self._handle_event
        self._command_task.start()

        self._logger = logging.getLogger('virtual_iface.bled112')
        self._logger.addHandler(logging.NullHandler())

        self.connected = False
        self._connection_handle = 0
        self._device = None

        #Initialize state
        self.payload_notif = False
        self.header_notif = False
        self.streaming = False

        self.rpc_payload = bytearray(20)
        self.rpc_header = bytearray(20)

        try:
            self.initialize_system_sync()
        except:
            self.stop_sync()
            raise

    @classmethod
    def find_bled112_devices(cls):
        found_devs = []

        #Look for BLED112 dongles on this computer and start an instance on each one
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if not hasattr(p, 'pid') or not hasattr(p, 'vid'):
                continue

            #Check if the device matches the BLED112's PID/VID combination
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

        self.device = device

        self._command_task.sync_command(['_set_advertising_data', 0, self._advertisement()])
        self._command_task.sync_command(['_set_advertising_data', 1, self._scan_response()])
        self._command_task.sync_command(['_set_mode', 0, 0]) #Disable advertising
        self._command_task.sync_command(['_set_mode', 4, 2]) #Enable undirected connectable

    def stop(self):
        """Safely shut down this interface
        """

        self._command_task.sync_command(['_set_mode', 0, 0]) #Disable advertising
        self.stop_sync()

    def _advertisement(self):
        flags = (0 << 1) | (0 << 2) | (int(self.device.pending_data))
        ble_flags = struct.pack("<BBB", 2, 1, 0x4 | 0x2) #General discoverability and no BR/EDR support
        uuid_list = struct.pack("<BB16s", 17, 6, TileBusService.bytes_le)
        manu = struct.pack("<BBHLH", 9, 0xFF, ArchManuID, self.device.iotile_id, flags)

        return ble_flags + uuid_list + manu

    def _scan_response(self):
        header = struct.pack("<BBH", 19, 0xFF, ArchManuID)
        voltage = struct.pack("<H", int(3.8*256)) #FIXME: Hardcoded 3.8V voltage
        reading = struct.pack("<HLLL", 0xFFFF, 0, 0, 0)
        name = struct.pack("<BB6s", 7, 0x09, "IOTile")
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

    def _handle_event(self, event):
        self._logger.debug("BLED Event: {}".format(str(event)))

        #Check if we're being connected to
        if event.command_class == 3 and event.command == 0:
            self.connected = True
            self._connection_handle = 0
            self._logger.info("Client connected")

        #Check if we're being disconnected from
        elif event.command_class == 3 and event.command == 4:
            self.connected = False
            self._connection_handle = 0
            self._command_task.async_command(['_set_mode', 4, 2], lambda x: None, {}) #Reenable advertising
            self._logger.info("Client disconnected, reenabling advertising")

        #Check for attribute writes that indicate interfaces being opened or closed
        elif event.command_class == 2 and event.command == 2:
            handle, flags = struct.unpack("<HB", event.payload)
            if handle == self.ReceiveHeaderHandle or handle == self.ReceivePayloadHandle and flags & 0b1:
                if handle == self.ReceiveHeaderHandle:
                    self.header_notif = True
                elif handle == self.ReceivePayloadHandle:
                    self.payload_notif = True

                if self.header_notif and self.payload_notif:
                    self.device.open_rpc_interface()
                    self._logger.info("RPC interface opened")
            elif handle == self.StreamingHandle:
                if flags & 0b1 and not self.streaming:
                    self.streaming = True
                    self.device.open_streaming_interface() #FIXME: Also stream back any accumulated reports here
                    self._logger.info("Streaming interface opened")
                elif not (flags & 0b1) and self.streaming:
                    self.streaming = False
                    self.device.close_streaming_interface()
                    self._logger.info("Streaming interface closed")

        #Now check for RPC writes
        elif event.command_class == 2 and event.command == 0:
            conn, reas, handle, offset, value = 