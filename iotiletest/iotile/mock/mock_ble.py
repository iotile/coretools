"""A Mock BLE device that will properly respond to RPCs, scripts and streaming over BLE"""

import struct
import uuid
import logging
from iotile.core.utilities import SharedLoop
from iotile.core.hw.reports import IOTileReading
from iotile.core.hw.exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import *


class CouldNotFindHandleError(IOTileException):
    """Raised when we could not find a BLE attribute handle"""
    pass


class UnsupportedReportFormat(IOTileException):
    """Raised when we receive a report from a MockIOTileDevice that we don't understand"""
    pass


class WriteToUnhandledCharacteristic(IOTileException):
    """Raised when we receive a write to a characteristics that we do not yet implement"""
    pass


class MockBLEDevice:
    """A mock implementation of a BLE based IOTile device

    All actual IOTile functionality is delegated to a MockIOTileDevice
    subclass.  This class should serve as the canonical reference class
    for the BLE interface to an IOTile device.

    Args:
        mac (string): MAC address of the BLE device
        device (MockIOTileDevice): object implementing actual IOTile functionality
    """

    ConnectableAdvertising = 0x00
    NonconnectableAdvertising = 0x02
    ScanResponsePacket = 0x04

    # BLE UUIDs for known services and characteristics
    TBService = uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')
    TBSendHeaderChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000320')
    TBSendPayloadChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000420')
    TBReceiveHeaderChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000120')
    TBReceivePayloadChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000220')
    TBStreamingChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000520')
    TBHighSpeedChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000620')

    ArchManuID = 0x03C0

    def __init__(self, mac, device):
        self.services = {}
        self.mac = mac

        self.device = device

        self._next_handle = 1

        self.handles = {}
        self.values = {}
        self.broadcast_reading = IOTileReading(0, 0xFFFF, 0)

        self.rssi = -50
        self.voltage = 3.8
        self.low_voltage_threshold = 3.2
        self.user_connected = False

        self.rpc_payload = b""

        self.logger = logging.getLogger('mock.ble.device')
        self._setup_iotile_service()

    @property
    def low_voltage(self):
        return self.voltage < self.low_voltage_threshold

    @property
    def advertisement_type(self):
        if self.user_connected:
            return self.NonconnectableAdvertising
        else:
            return self.ConnectableAdvertising

    def advertisement(self):
        flags = (int(self.low_voltage) << 1) | (int(self.user_connected) << 2) | (int(len(self.device.reports) > 0))
        ble_flags = struct.pack("<BBB", 2, 0, 0) #FIXME fix length
        uuid_list = struct.pack("<BB16s", 17, 6, self.TBService.bytes_le)
        manu = struct.pack("<BBHLH", 9, 0xFF, self.ArchManuID, self.device.iotile_id, flags)

        return ble_flags + uuid_list + manu

    def scan_response(self):
        header = struct.pack("<BBH", 19, 0xFF, self.ArchManuID)
        voltage = struct.pack("<H", int(self.voltage*256))
        reading = struct.pack("<HLLL", self.broadcast_reading.stream, self.broadcast_reading.value,
                              self.broadcast_reading.raw_time, 0)
        name = struct.pack("<BB6s", 7, 0x09, b"IOTile")
        reserved = struct.pack("<BBB", 0, 0, 0)

        response = header + voltage + reading + name + reserved
        assert len(response) == 31

        return response

    def add_char(self, service_id, char_id, can_notify):
        """Create entries in GATT table for a characteristics

        Args:
            service_id (uuid.UUID): The serviec this charateristics is part of
            char_id (uuid.UUID): The UUID of the characteristics
            can_notify (bool): Whether notifications are supported
        """

        handle = self._next_handle
        self._next_handle += 1

        if service_id not in self.services:
            self.services[service_id] = {}

        service = self.services[service_id]

        val = (handle, 'char')
        if char_id not in service:
            service[char_id] = []

        char = service[char_id]
        char.append(val)
        self.handles[handle] = val

        # Add in the value of this characteristic declaration
        self.values[handle] = self._make_char_decl({'uuid': char_id, 'value_handle': handle+1,
                                                    'properties': int(can_notify) << 4})

        handle = self._next_handle
        self._next_handle += 1

        val = (handle, 'value')
        char.append(val)
        self.handles[handle] = val

        if can_notify:
            handle = self._next_handle
            self._next_handle += 1

            val = (handle, 'config')
            char.append(val)
            self.handles[handle] = val
            self.values[handle] = struct.pack("<H", 0)

    def _setup_iotile_service(self):
        self.add_char(self.TBService, self.TBSendHeaderChar, False)
        self.add_char(self.TBService, self.TBSendPayloadChar, False)
        self.add_char(self.TBService, self.TBReceiveHeaderChar, True)
        self.add_char(self.TBService, self.TBReceivePayloadChar, True)
        self.add_char(self.TBService, self.TBStreamingChar, True)
        self.add_char(self.TBService, self.TBHighSpeedChar, False)

    def _make_char_decl(self, info):
        uuid_bytes = info['uuid'].bytes_le
        handle = info['value_handle']
        props = info['properties']

        return struct.pack("<BH%ds" % len(uuid_bytes), props, handle, uuid_bytes)

    def find_uuid(self, handle):
        for serv_uuid, serv  in self.services.items():
            for char_uuid, handles in serv.items():
                for iterhandle, handle_type in handles:
                    if iterhandle == handle:
                        return char_uuid, handle_type

        raise ValueError("Could not find UUID for handle %d" % handle)

    def find_handle(self, uuid, desired_type='value'):
        for _, serv  in self.services.items():
            for char_uuid, handles in serv.items():
                if char_uuid != uuid:
                    continue

                for iterhandle, handle_type in handles:
                    if handle_type == desired_type:
                        return iterhandle

        raise ValueError("Could not find handle by UUID: %s" % str(uuid))

    @property
    def gatt_services(self):
        return self.services.keys()

    def iter_handles(self, start, end):
        for key, val in self.handles.items():
            if start <= key <= end:
                yield val

    def min_handle(self, service):
        return min([min(x, key=lambda y: y[0]) for x in self.services[service].values()])[0]

    def max_handle(self, service):
        return max([max(x, key=lambda y: y[0]) for x in self.services[service].values()])[0]

    def read_handle(self, handle):
        if handle in self.values:
            return self.values[handle]

        #FIXME: Actually ask the subclass for the handle value here
        return bytearray(20)

    def write_handle(self, handle, value):
        """Process a write to a BLE attribute by its handle

        This function handles all writes from clients to the the MockBLEDevice.
        It keeps track of what handles correspond with special IOTIle service
        actions and dispatches them to a MockIOTileObject as needed.

        Args:
            handle (int): The handle to the attribute in the GATT table
            value (bytearry): The value to be written to the attribute

        Returns:
            tuple: A two item tuple with a bool indicating if the write succeeded and
                a (possibly empty) list of notifications that should be triggered because
                of this write.
        """

        char_id, handle_type = self.find_uuid(handle)

        # Check if this attribute is managed internally and if so update its value
        # If we are triggering IOTile actions by enabling notifications on specific characteristics,
        # notify the underlying device
        if handle in self.values:
            self.values[handle] = value

            # Check if we enabled notifications on both RPC responses
            if char_id == self.TBReceiveHeaderChar or char_id == self.TBReceivePayloadChar:
                if self.notifications_enabled(self.TBReceiveHeaderChar) and self.notifications_enabled(self.TBReceivePayloadChar):
                    self.logger.info("Opening RPC interface on mock device")
                    SharedLoop.run_coroutine(self.device.open_interface('rpc'))
                    return True, []

            elif char_id == self.TBStreamingChar and self.notifications_enabled(self.TBStreamingChar):
                self.logger.info("Opening Streaming interface on mock device")
                reports = SharedLoop.run_coroutine(self.device.open_interface('streaming'))
                if reports is None:
                    reports = []

                self.logger.info("Received %d reports from mock device", len(reports))

                return True, self._process_reports(reports)

            return True, []

        return self._handle_write(char_id, value)

    def _handle_write(self, char_id, value):
        if char_id == self.TBHighSpeedChar:
            self.device.push_script_chunk(value)
            return True, []
        elif char_id == self.TBSendPayloadChar:
            self.rpc_payload = value
            return True, []
        elif char_id == self.TBSendHeaderChar:
            return True, self._call_rpc(value)

        self.logger.info("Received write on unknown characteristic: {}".format(char_id))
        raise WriteToUnhandledCharacteristic("write on unknown characteristic", char_id=char_id, value=value)

    def _call_rpc(self, header):
        length, _, cmd, feature, address = struct.unpack("<BBBBB", bytes(header))
        rpc_id = (feature << 8) |  cmd

        self.logger.info("Calling RPC 0x%x at address %d", rpc_id, address)

        payload = self.rpc_payload[:length]

        status = 0
        try:
            response = SharedLoop.run_coroutine(self.device.async_rpc(address, rpc_id, bytes(payload)))
        except (RPCInvalidIDError, RPCNotFoundError):
            status = 1 #FIXME: Insert the correct ID here
            response = b""
        except TileNotFoundError:
            status = 0xFF
            response = b""

        resp_header = struct.pack("<BBBB", status, 0, 0, len(response))

        if len(response) > 0:
            return [(self.find_handle(self.TBReceiveHeaderChar), resp_header), (self.find_handle(self.TBReceivePayloadChar), response)]

        return [(self.find_handle(self.TBReceiveHeaderChar), resp_header)]

    def _process_reports(self, reports):
        """Process a list of sensor graph reports into notifications
        """

        notifs = []

        if reports is None:
            return notifs

        for report in reports:
            data = report.encode()
            if len(data) > 20:
                raise UnsupportedReportFormat("Report data too long to fit in one notification packet, length={}".format(len(data)))

            notifs.append((self.find_handle(self.TBStreamingChar), data))

        return notifs

    def notifications_enabled(self, handle_id):
        handle = self.find_handle(handle_id, 'config')
        value, = struct.unpack("<H", self.values[handle])

        if value & 0b1:
            return True

        return False
