"""A Mock BLE device that will properly respond to RPCs, scripts and streaming over BLE"""

import struct
import logging
from iotile.core.hw.reports import IOTileReading
from iotile.core.hw.exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import IOTileException
from ..interface import BLEAdvertisement, errors
from ..defines import AdvertisementType
from .constants import TileBusService, ARCH_MANUFACTURER
from .emulated_gatt_db import EmulatedGattTable


class UnsupportedReportFormat(IOTileException):
    """Raised when we receive a report from a MockIOTileDevice that we don't understand"""
    pass


class EmulatedBLEDevice:
    """A Bluetooth emulation layer wrapped around a VirtualDevice

    All actual IOTile functionality is delegated to a VirtualDevice subclass.
    This class should serve as the canonical reference class for the BLE
    interface to an IOTile device.

    Args:
        mac (str): MAC address of the BLE device
        device (VirtualDevice): object implementing actual IOTile functionality
    """

    def __init__(self, mac, device, *, voltage=3.8, rssi=-50, low_voltage=False):
        self.mac = mac

        self.device = device
        self.gatt_table = EmulatedGattTable()
        self.user_connected = False

        self._broadcast_reading = IOTileReading(0, 0xFFFF, 0)
        self._rssi = rssi
        self._voltage = voltage
        self._low_voltage = low_voltage

        self.rpc_payload = b""

        self.logger = logging.getLogger(__name__)
        self._setup_iotile_service()

    def _setup_iotile_service(self):
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.SEND_HEADER, write=True, write_no_response=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.SEND_PAYLOAD, write=True, write_no_response=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.RECEIVE_HEADER, read=True, notify=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.RECEIVE_PAYLOAD, read=True, notify=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.STREAMING, read=True, notify=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.HIGHSPEED, read=True, notify=True)

        self.gatt_table.update_handles()

    def advertisement(self) -> BLEAdvertisement:
        """Get the latest advertisement data from the device."""

        return _build_v1_advertisement(self.mac, self._rssi, self.device.iotile_id, self.user_connected,
                                       False, self._voltage, self._low_voltage, self._broadcast_reading)

    async def read_handle(self, handle):
        """Read the current value of a handle."""
        return self.gatt_table.raw_handles[handle - 1].raw_value

    async def write_handle(self, handle, value):
        """Process a write to a BLE attribute by its handle

        This function handles all writes from clients to the the MockBLEDevice.
        It keeps track of what handles correspond with special IOTIle service
        actions and dispatches them to a MockIOTileObject as needed.

        Args:
            handle (int): The handle to the attribute in the GATT table
            value (bytes): The value to be written to the attribute

        Returns:
            list of bytes: A list of the notifications that should be triggered by this write.
        """

        attribute, parent_char = self.gatt_table.lookup_handle(handle)
        char_id = parent_char.uuid

        # Check if this attribute is managed internally and if so update its value
        # If we are triggering IOTile actions by enabling notifications on specific characteristics,
        # notify the underlying device
        attribute.raw_value = value
        self.logger.info("Wrote value %r to handle %d", value, handle)

        # Check if we enabled notifications on both RPC responses
        if char_id in (TileBusService.RECEIVE_PAYLOAD, TileBusService.RECEIVE_HEADER):
            if (self.notifications_enabled(TileBusService.RECEIVE_PAYLOAD) and
                    self.notifications_enabled(TileBusService.RECEIVE_HEADER)):
                self.logger.info("Opening RPC interface on mock device")
                await self.device.open_interface('rpc')

            return []

        if char_id == TileBusService.STREAMING:
            if self.notifications_enabled(TileBusService.STREAMING):
                self.logger.info("Opening Streaming interface on mock device")
                reports = await self.device.open_interface('streaming')
                if reports is None:
                    reports = []

                self.logger.info("Received %d reports from mock device", len(reports))

                return self._process_reports(reports)

            return []

        if char_id == TileBusService.HIGHSPEED:
            self.device.push_script_chunk(value)
            return []

        if char_id == TileBusService.SEND_PAYLOAD:
            self.rpc_payload = value
            return []

        if char_id == TileBusService.SEND_HEADER:
            return await self._call_rpc(value)

        self.logger.info("Received write on unknown characteristic: %s with handle %d", char_id, handle)
        raise errors.InvalidHandleError("Unknown characteristic: %s" % char_id, handle)

    async def _call_rpc(self, header):
        length, _, cmd, feature, address = struct.unpack("<BBBBB", bytes(header))
        rpc_id = (feature << 8) |  cmd

        self.logger.info("Calling RPC 0x%x at address %d", rpc_id, address)

        payload = self.rpc_payload[:length]

        status = 0
        try:
            #FIXME: Use modern conversion routines here to get tilebus codes
            response = await self.device.async_rpc(address, rpc_id, bytes(payload))
        except (RPCInvalidIDError, RPCNotFoundError):
            status = 1 #FIXME: Insert the correct ID here
            response = b""
        except TileNotFoundError:
            status = 0xFF
            response = b""

        resp_header = struct.pack("<BBBB", status, 0, 0, len(response))

        header_handle = self.gatt_table.find_char(TileBusService.RECEIVE_HEADER).value.handle
        payload_handle = self.gatt_table.find_char(TileBusService.RECEIVE_PAYLOAD).value.handle
        if len(response) > 0:
            return [(header_handle, resp_header), (payload_handle, response)]

        return [(header_handle, resp_header)]

    def _process_reports(self, reports):
        """Process a list of sensor graph reports into notifications
        """

        notifs = []

        if reports is None:
            return notifs

        streaming_handle = self.gatt_table.find_char(TileBusService.STREAMING).value.handle

        for report in reports:
            data = report.encode()
            if len(data) > 20:
                raise UnsupportedReportFormat("Report data too long to fit in one notification packet, length={}".format(len(data)))

            notifs.append((streaming_handle, data))

        return notifs

    def notifications_enabled(self, char_uuid):
        char = self.gatt_table.find_char(char_uuid)
        return char.is_subscribed('notify')


def _v1_advert_type(user_connected):
    #FIXME: Make sure this actually matches the advertisement types used in real devices
    if user_connected:
        return AdvertisementType.NONCONNECTABLE

    return AdvertisementType.CONNECTABLE


def _v1_advert_data(iotile_id, user_connected, has_data, low_voltage):
    flags = (int(low_voltage) << 1) | (int(user_connected) << 2) | (int(has_data))
    ble_flags = struct.pack("<BBB", 2, 0, 0) #FIXME fix length
    uuid_list = struct.pack("<BB16s", 17, 6, TileBusService.UUID.bytes_le)
    manu = struct.pack("<BBHLH", 9, 0xFF, ARCH_MANUFACTURER, iotile_id, flags)

    return ble_flags + uuid_list + manu


def _v1_scan_response_data(voltage, broadcast_reading):
    header = struct.pack("<BBH", 19, 0xFF, ARCH_MANUFACTURER)
    voltage = struct.pack("<H", int(voltage*256))
    reading = struct.pack("<HLLL", broadcast_reading.stream, broadcast_reading.value,
                          broadcast_reading.raw_time, 0)
    name = struct.pack("<BB6s", 7, 0x09, b"IOTile")
    reserved = struct.pack("<BBB", 0, 0, 0)

    response = header + voltage + reading + name + reserved
    assert len(response) == 31

    return response


def _build_v1_advertisement(address, rssi, iotile_id, user_connected, has_data,
                            voltage, low_voltage, broadcast_reading):

    advert = _v1_advert_data(iotile_id, user_connected, has_data, low_voltage)
    scan_response = _v1_scan_response_data(voltage, broadcast_reading)
    kind = _v1_advert_type(user_connected)

    return BLEAdvertisement(address, kind, rssi, advert, scan_response)
