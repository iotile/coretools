import logging
import asyncio
import time
import struct
from typing import Dict, Optional, Union
from uuid import UUID
import serial
from iotile.core.utilities.async_tools import BackgroundEventLoop, SharedLoop
from iotile.core.hw.exceptions import DeviceAdapterError
from serial import Serial
from iotile_transport_blelib.support import BLEScanManager
from iotile_transport_blelib.interface import (AbstractBLECentral, BLEScanDelegate, BLEAdvertisement,
                                               BLEPeripheral, BLEPeripheralDelegate, errors, BLECentralState)
from iotile_transport_blelib.interface.peripheral_delegate import EmptyPeripheralDelegate
from iotile_transport_blelib.interface.scan_delegate import EmptyScanDelegate
from .bled112_peripheral import BLED112Peripheral
from .async_bled112 import AsyncBLED112
from ..utilities import open_bled112
from . import packets


class _ConnectionData:
    def __init__(self, conn_string: str, handle: int,
                 delegate: Optional[BLEPeripheralDelegate], peripheral: Optional[BLED112Peripheral]):
        self.conn_string = conn_string
        self.conn_handle = handle
        self.delegate = delegate
        self.peripheral = peripheral


class BLED112Central(AbstractBLECentral):
    _bled112 = None  # type: AsyncBLED112
    _serial = None  #type: Serial

    def __init__(self, device: Union[serial.Serial, str], loop: BackgroundEventLoop = SharedLoop):
        self._logger = logging.getLogger(__name__)

        if device is None or isinstance(device, str):
            device = open_bled112(device, self._logger, timeout=1.0)

        self._serial = device
        self._loop = loop
        self._tracked_conns = {}  # type: Dict[int, _ConnectionData]
        self._scanners = BLEScanManager()

    def on_disconnect(self, packet: packets.DisconnectionPacket):
        data = self._tracked_conns.get(packet.conn)
        if data is None:
            self._logger.debug("Dropping disconnection notice from untracked connection "
                               "(handle: %d, reason: 0x%X)", packet.conn, packet.reason)
            return

        del self._tracked_conns[packet.conn]
        self._logger.debug("Received disconnect from device %s because of reason 0x%X",
                           data.conn_string, packet.reason)

        if len(self._tracked_conns) == 0:
            self._loop.launch_coroutine(self._ensure_correct_scan_mode())

        expected = (packet.reason == 0 or packet.reason == 0x216)

        if data.delegate is not None and data.peripheral is not None:
            data.delegate.on_disconnect(data.peripheral, expected)

    async def _ensure_not_scanning(self):
        try:
            await self._bled112.stop_scan()
            self._scanners.scan_stopped()
        except DeviceAdapterError:
            # If we errored our it is because we were not currently scanning
            pass

    async def _ensure_correct_scan_mode(self, attempt=0):
        try:
            if attempt > 0:
                await asyncio.sleep(0.1)
                await self._ensure_not_scanning()
            elif self._scanners.should_stop() or self._scanners.should_restart():
                await self._ensure_not_scanning()

            if self._scanners.should_start() and len(self._tracked_conns) == 0:
                active = self._scanners.active_scan()
                await self._bled112.start_scan(active)
                self._scanners.scan_started(active)
        except:
            self._logger.warning("Failed to set correct scan mode on attempt %d, trying again later",
                                 attempt + 1, exc_info=True)
            self._loop.launch_coroutine(self._ensure_correct_scan_mode(attempt + 1))
            # FIXME: After a certain number of attempts to ensure the right scan mode, raise a fatal error

    async def start(self):
        self._bled112 = AsyncBLED112(self._serial, self._loop)

        max_connections, active_conns = await self._bled112.query_systemstate()

        for conn in active_conns:
            try:
                await self._bled112.disconnect(conn.conn_handle)
            except:
                self._logger.error("Error disconnecting connection handle %d (%s) on start",
                                   conn.conn_handle, conn.connection_string)
                raise

        # If the dongle was previously left in a dirty state while still scanning, it will
        # not allow new scans to be started.  So, forcibly stop any in progress scans.
        await self._ensure_not_scanning()

        # Disable advertising in case we were previously used as a ble peripheral
        await self._bled112.set_mode(0, 0)

        # Setup callbacks
        self._bled112.operations.every_match(self.on_advertisement, class_=6, cmd=0, event=True)
        self._bled112.operations.every_match(self.on_disconnect, class_=3, cmd=4, event=True)

        self._logger.info("Started BLED112 adapter supporting %d connections",
                          max_connections)

    async def stop(self):
        self._scanners.release_all()
        await self._ensure_not_scanning()

        # Forcible disconnect any active connections that we have going
        _, active_conns = await self._bled112.query_systemstate()
        for conn in active_conns:
            await self._bled112.disconnect(conn.conn_handle)

        await self._bled112.stop()

    async def connect(self, conn_string: str, delegate: Optional[BLEPeripheralDelegate] = None) -> BLEPeripheral:
        """
        """

        start_time = time.monotonic()

        handle = await self._bled112.connect(conn_string)

        try:
            table = await self._bled112.probe_gatt_table(handle)
        except errors.DisconnectionError:
            raise
        except errors.LinkError:
            try:
                await self._bled112.disconnect(handle)
            except:  #pylint:disable=bare-except;We want to raise the original error; this one is logged.
                self._logger.exception("Error disconnecting from device during failed gatt table probe")

            raise

        end_time = time.monotonic()
        self._logger.info("Total time to connect to device %.3f", end_time - start_time)

        peripheral = BLED112Peripheral(conn_string, handle, table)
        if delegate is None:
            delegate = EmptyPeripheralDelegate()

        data = _ConnectionData(conn_string, handle, delegate, peripheral)
        self._tracked_conns[handle] = data

        return peripheral

    async def disconnect(self, peripheral: BLEPeripheral):
        """
        """

        data = self._ensure_connected(peripheral)

        # Connection is cleaned up by disconnect handler
        await self._bled112.disconnect(data.conn_handle)
        assert data.conn_handle not in self._tracked_conns

    async def set_notifications(self, peripheral: BLEPeripheral, characteristic: UUID,
                                enabled: bool, kind: str = 'notify'):
        """
        """

        if kind not in ('notify', 'indicate'):
            raise errors.UnsupportedOperationError("Invalid notification type: %s" % kind)

        if kind != 'notify':
            raise errors.UnsupportedOperationError("Cannot configure notification type %s" % kind)

        data = self._ensure_connected(peripheral)
        await self._bled112.set_subscription(data.conn_handle, peripheral.find_char(characteristic),
                                             kind, enabled)

    async def write(self, peripheral: BLEPeripheral, characteristic: UUID,
                    value: bytes, with_response: bool):
        """
        """

        data = self._ensure_connected(peripheral)
        handle = peripheral.prepare_write(characteristic, value)
        await self._bled112.write_handle(data.conn_handle, handle, with_response, value)

    async def read(self, peripheral: BLEPeripheral, characteristic: UUID):
        """
        """

        #FIXME: Raise an exception here

    async def request_scan(self, tag: str, active: bool, delegate: BLEScanDelegate = None):
        """
        """

        if delegate is None:
            delegate = EmptyScanDelegate()

        self._scanners.request(tag, delegate, active)
        await self._ensure_correct_scan_mode()

    async def release_scan(self, tag: str):
        """
        """

        self._scanners.release(tag)
        await self._ensure_correct_scan_mode()

    async def state(self) -> BLECentralState:
        """
        """

        max_conns, active_conns = await self._bled112.query_systemstate()
        return BLECentralState(max_conns, active_conns)

    async def on_advertisement(self, packet: packets.BGAPIPacket):
        """Handle the receipt of an advertising packet."""

        try:
            payload = packet.payload
            length = len(payload) - 10
            rssi, packet_type, sender, _, _, data = struct.unpack("<bB6sBB%ds" % length, payload)
            string_address = ':'.join([format(x, "02X") for x in bytearray(sender[::-1])])

            # FIXME: Check for scan response data and process it as well (packet type = 4)
            if packet_type not in (0, 2, 6):
                return

            advert = BLEAdvertisement(string_address, packet_type, rssi, data)
            self._scanners.handle_advertisement(advert)
        except:  #pylint:disable=bare-except;This is called in a background handler and logs the error
            self._logger.debug("Error processing advertisement, data=%s", payload, exc_info=True)

    def _ensure_connected(self, peripheral: BLEPeripheral) -> _ConnectionData:
        if not isinstance(peripheral, BLED112Peripheral):
            raise errors.UnsupportedOperationError("Peripheral object did not come from this ble adapter")

        data = self._tracked_conns.get(peripheral.conn_handle)
        if data is None:
            raise errors.InvalidStateError("No known connection for %s" % peripheral.connection_string)

        return data
