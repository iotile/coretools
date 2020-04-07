"""Generic BLE Central that emulates the operation of any AbstractBLECentral device.

The purpose of this class is to test bluetooth device adapter implementations and
verify that the properly handle all core bluetooth operations.
"""

import logging
import asyncio
from uuid import UUID
from typing import Iterable, Optional, Dict
from typing_extensions import TypedDict
from iotile.core.utilities.async_tools import OperationManager, SharedLoop
from ...interface import messages, errors, BLEAdvertisement, GattCharacteristic, BLEPeripheral
from ...support import BLEScanManager
from .emulated_device import EmulatedBLEDevice



EmulatedCentralOptions = TypedDict('EmulatedCentralOptions', {
    'advertisement_rate': float
}, total=False)

DEFAULT_CENTRAL_OPTIONS = {
    'advertisement_rate': 0.1
}  #type: EmulatedCentralOptions


class _EmulatedDeviceChannel:
    def __init__(self, central: 'EmulatedBLECentral'):
        self._central = central

    async def notify(self, characteristic: GattCharacteristic, value: bytes, indicate: bool):
        pass

    async def disconnect(self):
        pass

    async def update_advertisement(self, advertisement: BLEAdvertisement):
        self._central._latest_advertisements[advertisement.sender] = advertisement
        self._central._send_advertisement(advertisement)


class EmulatedBLECentral:
    """Emulated BLE central implementation.

    This class can be loaded with EmulatedBLEDevice objects and will
    provide access to them using normal ble operations.

    It functions as a complete reference implementation of a Bluetooth Low
    Energy controller in observer or central mode.
    """

    def __init__(self, devices: Iterable[EmulatedBLEDevice], options: Optional[EmulatedCentralOptions] = None, *,
                 loop=SharedLoop):
        self.devices = {device.mac: device for device in devices}  #type: Dict[str, EmulatedBLEDevice]
        self.connections = {}  #type: Dict[str, BLEPeripheral]
        self.events = OperationManager(loop=loop)  #type: OperationManager[messages.BluetoothEvent]

        self._options = options
        self._logger = logging.getLogger(__name__)

        self._advertisement_task = None
        self._latest_advertisements = {}  #type: Dict[str, BLEAdvertisement]
        self._scan_manager = BLEScanManager(self.events)
        self._loop = loop

    async def start(self):
        started = []

        try:
            channel = _EmulatedDeviceChannel(self)
            for device in self.devices.values():
                await device.start(channel)
                started.append(device)
        except:
            self._logger.warning("Error starting ble central", exc_info=True)
            for device in started:
                try:
                    await device.stop()
                except:
                    self._logger.warning("Error stopping prior device in subsequent start() error", exc_info=True)

            raise

        self._advertisement_task = asyncio.ensure_future(self._advertiser())

    async def stop(self):
        self._advertisement_task.cancel()
        await self._advertisement_task

        for device in self.devices.values():
            await device.stop()

    async def request_scan(self, tag: str, active: bool):
        """Request that the BLE Central scan for ble devices.

        For ease of testing, all advertisements are sent immediately before
        this method finishes as well as being sent periodically.
        """

        self._scan_manager.request(tag, active)
        if self._scan_manager.should_restart():
            self._scan_manager.scan_started(self._scan_manager.active_scan())

        self._send_all_advertisements()

    async def release_scan(self, tag: str):
        """Release a previous scan request.

        If scan information is no longer needed, this method may be called to
        stop receiving advertisements.  Callbacks on the corresponding scan
        delegate will immediately cease and the BLE central should stop
        scanning as soon as it is able to if there are no other active scan
        requesters.
        """

        self._scan_manager.release(tag)

        if self._scan_manager.should_stop():
            self._scan_manager.scan_stopped()
        elif self._scan_manager.should_restart():
            self._scan_manager.scan_stopped()
            self._scan_manager.scan_started(self._scan_manager.active_scan())

            self._send_all_advertisements()

    async def connect(self, conn_string: str) -> BLEPeripheral:
        """Connect to a peripheral device.

        This method should perform a combined BLE connect and gatt table probe
        operations. Depending on the underlying central hardware, those
        operations may already be fused together, or a sequence of operations
        may need to be performed inside the implemenation of this method
        before returning a BLEPeripheral subclass that has a complete GATT
        table.

        The connection string used should exactly match a connection string
        received as part of a previous advertisement packet.  If the user
        knows the connection string format for a given BLE central
        implementation, they may construct it explicitly to indicate what
        device they wish to connect to.

        This operation does not natively timeout and should be explicitly
        cancelled by the user if it takes too long to connect to the device
        they wish to reach.
        """

        ble_dev = self.devices.get(conn_string)
        if ble_dev is None or ble_dev.device.connected:
            self._logger.warning("Attempted to connect to device %s that is not connectable, waiting for 30 seconds",
                                 conn_string)
            await asyncio.sleep(60)  # This is an arbitrary long wait because the caller should explicitly cancel
            raise asyncio.TimeoutError("Timeout trying to connect to nonconnectable device, "
                                       "this should have already been cancelled before this point")

        await ble_dev.device.connect()

        periph = BLEPeripheral(conn_string, ble_dev.gatt_table)
        self.connections[conn_string] = periph

        return periph

    async def disconnect(self, conn_string: str):
        """Disconnect from a connected peripheral device."""

        self._ensure_connected(conn_string, 'disconnect')

        ble_dev = self.devices.get(conn_string)
        if ble_dev is None or not ble_dev.device.connected:
            raise errors.NotConnectedError('disconnect', conn_string)

        await ble_dev.device.disconnect()

    async def manage_subscription(self, conn_string: str, characteristic: UUID,
                                  enabled: bool, acknowledged: bool = False):
        """Enable or disable notifications/indications on a characteristic.

        This method allows you to control the notification status on any GATT
        characteristic that supports either notifications or indications.

        If you pass acknowledged = False, the default, then notifications will
        be enabled/disabled.

        If you pass acknowledged = True, then indications will be enabled/disabled.
        """

        peripheral = self._ensure_connected(conn_string, 'manage_subscription')

        if acknowledged is True:
            raise errors.UnsupportedOperationError("Indications are not supported in EmualatedBLECentral")

        char = _find_char(peripheral, characteristic, conn_string)

        if char.client_config is None or not char.can_subscribe():
            raise errors.GattError("Characteristic %s does not support notifications" % characteristic,
                                   conn_string)

        # Only write values remotely if they have changed based on the local cache
        if char.modify_subscription(enabled=enabled):
            self._logger.debug("Updating notification status on %s to %s for %s",
                               characteristic, enabled, conn_string)
            device = self.devices[conn_string]
            await device.write_handle(char.client_config.handle, char.client_config.raw_value)

    async def write(self, conn_string: str, characteristic: UUID,
                    value: bytes, with_response: bool = False):
        """Write the value of a characteristic.

        You can specify whether the write is acknowledged or unacknowledged.
        Unacknowledged writes may fail with QueueFullError if there is not
        space inside the host controller to hold the write until the next
        connection event.  This error is not fatal and indicates that the
        caller should backoff and try again later.
        """

        peripheral = self._ensure_connected(conn_string, 'write')

        char = _find_char(peripheral, characteristic, conn_string)
        char.value.raw_value = value

        device = self.devices[conn_string]
        await device.write_handle(char.value.handle, char.value.raw_value)

    def _ensure_connected(self, conn_string, operation) -> BLEPeripheral:
        """Helper function to protect operations requiring a connection."""

        if conn_string not in self.connections:
            raise errors.NotConnectedError(operation, conn_string)

        return self.connections[conn_string]

    def _send_all_advertisements(self):
        if not self._scan_manager.is_scanning():
            return

        for advert in self._latest_advertisements.values():
            self._send_advertisement(advert)

    def _send_advertisement(self, advert: BLEAdvertisement):
        if not self._scan_manager.active_scan():
            advert = _strip_scan_response(advert)

        self._scan_manager.handle_advertisement(advert)

    async def _advertiser(self):
        sleep_time = _pick('advertisement_rate', self._options)

        self._logger.debug("Starting emulated ble central advertisement task with %.0fms interval", sleep_time * 1000.0)

        while True:
            try:
                await asyncio.sleep(sleep_time)
                self._send_all_advertisements()
            except asyncio.CancelledError:
                break
            except:
                self._logger.exception("Error eaten in background periodic advertiser routine")


def _pick(key: str, options: Optional[EmulatedCentralOptions]):
    """Helper function to get specified or default options."""

    if options is not None and key in options:
        return options.get(key)

    return DEFAULT_CENTRAL_OPTIONS.get(key)


def _strip_scan_response(advert: BLEAdvertisement) -> BLEAdvertisement:
    if advert.scan_response is None:
        return advert

    return BLEAdvertisement(advert.sender, advert.kind, advert.rssi, advert.advertisement)


def _find_char(peripheral, char_uuid, conn_string):
    if peripheral.gatt_table is None:
        raise errors.GattError("Missing GATT table, cannot manage subscription", conn_string)

    try:
        return peripheral.gatt_table.find_char(char_uuid)
    except Exception as err:
        raise errors.GattError("Could not find characteristic %s in GATT table" % char_uuid,
                               conn_string) from err
