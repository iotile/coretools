"""A Mock BLE device that will properly respond to RPCs, scripts and streaming over BLE"""

import struct
import asyncio
from typing import Protocol
import logging
from iotile.core.hw.reports import IOTileReading
from iotile.core.hw.virtual import AbstractAsyncDeviceChannel
from iotile.core.hw.exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import IOTileException
from iotile.core.utilities import SharedLoop
from ...interface import BLEAdvertisement, errors, GattCharacteristic
from ...defines import AdvertisementType
from ..constants import TileBusService
from ..advertisements import generate_advertisement
from .emulated_gatt import EmulatedGattTable


class _BLEVirtualDeviceChannel(AbstractAsyncDeviceChannel):
    def __init__(self):
        pass

    async def stream(self, report):
        """Stream a report to the client.

        Raises:
            DevicePushError: The report could not be streamed/queued for streaming.
        """

    async def trace(self, data):
        """Send binary tracing data to the client.

        Raises:
            DevicePushError: The tracing data could not be send/queued for sending.
        """

    async def disconnect(self):
        """Forcibly disconnect the connected client.

        Raises:
            DevicePushError: If there is no client connected or they could not be disconnected.
        """


class BLEPeripheralChannel(Protocol):
    """Required operations that a BLE peripheral interface must support."""

    async def notify(self, characteristic: GattCharacteristic, value: bytes, indicate: bool):
        """Notify or indicate a changed characteristic value.

        The semantics of this method that must be respected are:
        - If ``indicate`` is False, then this method should block until the notification
          is successfully queued for transmission.  If queuing is not possible, an
          exception can be raised.
        - If ``indicate`` is True, then this method should block until the indication is
          positively acknowledged by the remote party.

        Args:
            characteristic: The characteristic that the notification or indication is
                happening on.  Note that the characteristic is passed instead of the
                integer handle in case some ble backends don't support direct GATT
                table operations.
            value: The value to send.
            indicate: Whether to send an indication.  If this is False, then a notification
                is sent instead.

        Raises:
            QueueFullError: The notification could not be queued due to a limited internal buffer.
            DisconnectionError: The remote side disconnected before the notification could be sent.
        """

    async def disconnect(self):
        """Disconnect the peer central device.

        This method should block until the disconnection occurs.
        """

    async def update_advertisement(self, advertisement: BLEAdvertisement):
        """Update the advertisement information that is being sent.

        This method should block until the update has been communicated to the
        BLE host controller.  Note that depending on the BLE controller
        hardware, it may ignore the ``sender`` address in the advertisement
        and use its own MAC address.

        Args:
            advertisement: The new advertisement data that should replace the previous data.
        """


class EmulatedBLEDevice:
    """A Bluetooth emulation layer wrapped around a VirtualDevice

    All actual IOTile functionality is delegated to a VirtualDevice subclass.
    This class should serve as the canonical reference class for the BLE
    interface to an IOTile device.

    Args:
        mac (str): MAC address of the BLE device
        device (VirtualDevice): object implementing actual IOTile functionality
    """

    def __init__(self, mac, device, *, voltage=3.8, rssi=-50, low_voltage=False, loop=SharedLoop):
        self.mac = mac

        self.device = device
        self.gatt_table = EmulatedGattTable()
        self.user_connected = False

        self._broadcast_reading = IOTileReading(0, 0xFFFF, 0)
        self._rssi = rssi
        self._voltage = voltage
        self._low_voltage = low_voltage

        self._channel = None  # type: BLEPeripheralChannel
        self._task = None
        self._queue = None
        self._loop = loop

        self.rpc_payload = b""

        self.logger = logging.getLogger(__name__)
        self._setup_iotile_service()

    async def start(self, channel: BLEPeripheralChannel):
        """Start this emulated device.

        You must pass in a channel to use to push information to the central peer.

        Args:
            channel: An object that allows for ble operations to be performed by this
                device.
        """

        # FIXME: Create a proper push channel
        adapted_channel = _BLEVirtualDeviceChannel()
        await self._loop.run_in_executor(self.device.start, adapted_channel)

        self._queue = asyncio.Queue()
        self._channel = channel
        self._task = asyncio.ensure_future(self._background_task())

        try:
            advert = generate_advertisement(self.device.iotile_id, 'v1', self.mac, self._rssi)
            await self._channel.update_advertisement(advert)
        except:
            await self.stop()
            raise

    async def stop(self):
        """Stop this emulated device."""

        self._task.cancel()
        await self._task

        await self._loop.run_in_executor(self.device.stop)

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
        """

        attribute, parent_char = self.gatt_table.lookup_handle(handle)
        char_id = parent_char.uuid

        # Check if this attribute is managed internally and if so update its value
        # If we are triggering IOTile actions by enabling notifications on specific characteristics,
        # notify the underlying device
        attribute.raw_value = value
        self.logger.debug("Wrote value %r to handle %d", value, handle)

        # Check if we enabled notifications on both RPC responses
        if char_id in (TileBusService.RECEIVE_PAYLOAD, TileBusService.RECEIVE_HEADER):
            if (self._notifications_enabled(TileBusService.RECEIVE_PAYLOAD) and
                    self._notifications_enabled(TileBusService.RECEIVE_HEADER)):
                self.logger.info("Opening RPC interface on mock device")
                await self.device.open_interface('rpc')

            return

        if char_id == TileBusService.STREAMING:
            if self._notifications_enabled(TileBusService.STREAMING):
                self.logger.info("Opening Streaming interface on mock device")
                reports = await self.device.open_interface('streaming')
                if reports is not None and len(reports) > 0:
                    self.logger.info("Received %d reports from device upon opening streaming interface",
                                     len(reports))
                    self._background_notify_reports(reports)

            return

        if char_id == TileBusService.HIGHSPEED:
            self.device.push_script_chunk(value)
            return

        if char_id == TileBusService.SEND_PAYLOAD:
            self.rpc_payload = value
            return

        if char_id == TileBusService.SEND_HEADER:
            await self._call_rpc(value)
            return

        self.logger.info("Received write on unknown characteristic: %s with handle %d", char_id, handle)
        raise errors.InvalidHandleError("Unknown characteristic: %s" % char_id, handle)

    def _setup_iotile_service(self):
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.SEND_HEADER, write=True, write_no_response=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.SEND_PAYLOAD, write=True, write_no_response=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.RECEIVE_HEADER, read=True, notify=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.RECEIVE_PAYLOAD, read=True, notify=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.STREAMING, read=True, notify=True)
        self.gatt_table.quick_add(TileBusService.UUID, TileBusService.HIGHSPEED, read=True, notify=True)

        self.gatt_table.update_handles()

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

        header_char = self.gatt_table.find_char(TileBusService.RECEIVE_HEADER)
        payload_char = self.gatt_table.find_char(TileBusService.RECEIVE_PAYLOAD)

        await self._queue.put((header_char, resp_header))
        if len(response) > 0:
            await self._queue.put((payload_char, response))

    def _background_notify_reports(self, reports):
        """Start streaming encoded reports in the background."""

        streaming_char = self.gatt_table.find_char(TileBusService.STREAMING)

        for report in reports:
            data = report.encode()
            self._queue.put_nowait((streaming_char, data))

    async def _background_task(self):
        try:
            while True:
                char, value = await self._queue.get()

                try:
                    await self._notify_in_chunks(self._channel.notify, char, value, self.logger)
                except errors.LinkError:
                    self.logger.debug("Stopped in-progress notification due to error", exc_info=True)
                except asyncio.CancelledError:
                    raise
                except:  #pylint:disable=bare-except;This is a background task that should not die.
                    self.logger.exception("Background notifier task failed for an unexcepted, non-ble error")
        except asyncio.CancelledError:
            return

    def _notifications_enabled(self, char_uuid):
        char = self.gatt_table.find_char(char_uuid)
        return char.is_subscribed('notify')


async def _notify_in_chunks(notify, char: GattCharacteristic, value: bytes, logger, backoff=0.05):
    """Notify a characteristic value handling backoff."""

    for i in range(0, len(value), 20):
        chunk = value[i:i + 20]

        success = False
        while not success:
            try:
                await notify(char, chunk)
            except errors.QueueFullError:
                await asyncio.sleep(backoff)
                continue
            except asyncio.CancelledError:
                # Don't log anything when we're cancelled, just stop notifying
                raise
            except:
                logger.debug("Stopping chunked notification on %s at %d/%d bytes because of failure",
                             char.uuid, i, len(value))
                raise
