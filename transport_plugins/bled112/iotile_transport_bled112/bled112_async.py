"""A DeviceAdapter that uses an attached jlink device for transport."""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import time
import threading
import datetime
import serial
import asyncio
from typing import Union
from typedargs.exceptions import ArgumentError
from iotile_transport_bled112 import bgapi_structures
from iotile.core.dev.config import ConfigManager
from iotile.core.utilities.packed import unpack
from iotile.core.exceptions import HardwareError
from iotile.core.hw.reports import IOTileReportParser, IOTileReading, BroadcastReport
from iotile.core.hw.transport.adapter import DeviceAdapter
from .hardware.async_central import BLED112Central
from iotile_transport_blelib.interface import errors, BLEAdvertisement, BLEPeripheral, GattCharacteristic
from .tilebus import TileBusService, TileBusStreamingCharacteristic, TileBusTracingCharacteristic, TileBusHighSpeedCharacteristic
from .utilities import open_bled112

from iotile.core.exceptions import HardwareError
from iotile.core.hw.exceptions import DeviceAdapterError
from iotile.core.hw.transport.adapter import StandardDeviceAdapter
from iotile.core.hw.reports import IOTileReportParser
from iotile.core.utilities import SharedLoop


class BLED112Adapter(StandardDeviceAdapter):
    """Asyncio based device adapter using a bled112 bluetooth dongle."""

    _central = None  # type: BLED112Central
    _serial_port = None  # type: serial.Serial
    _manages_serial_port = True

    def __init__(self, port: Union[str, serial.Serial], name=__name__, loop=SharedLoop, **kwargs):
        super(BLED112Adapter, self).__init__(name, loop)

        self.set_config('minimum_scan_time', 2.0)

        config = ConfigManager()

        self._active_scan = config.get('bled112:active-scan')
        self._throttle_broadcast = config.get('bled112:throttle-broadcast')
        self._throttle_scans = config.get('bled112:throttle-scan')
        self._throttle_timeout = config.get('bled112:throttle-timeout')

        # Prepare internal state of scannable and in progress devices
        # Do this before spinning off the BLED112CommandProcessor
        # in case a scanned device is seen immediately.
        self.partial_scan_responses = {}

        self._broadcast_state = {}
        self._connections = {}

        self.count_lock = threading.Lock()
        self.connecting_count = 0

        self._scan_event_count = 0
        self._v1_scan_count = 0
        self._v1_scan_response_count = 0
        self._v2_scan_count = 0
        self._device_scan_counts = {}
        self._last_reset_time = time.monotonic()

        if port is None or isinstance(port, str):
            self._port = port
        else:
            self._serial_port = port
            self._manages_serial_port = False

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

    async def start(self):
        """Start the device adapter.

        See :meth:`AbstractDeviceAdapter.start`.
        """

        if self._serial_port is None:
            self._serial_port = open_bled112(self._port, self._logger)

        self._central = BLED112Central(self._serial_port, loop=self._loop)

        await self._central.start()

        state = await self._central.state()
        self.set_config('max_connections', state.max_connections)

        await self._central.request_scan('adapter', self._active_scan, self)

    async def stop(self):
        """Stop the device adapter.

        See :meth:`AbstractDeviceAdapter.stop`.
        """

        await self._central.stop()

        if self._manages_serial_port:
            self._serial_port.close()

    async def connect(self, conn_id, connection_string):
        """Asynchronously connect to a device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.
        """

        retries = 4
        peripheral = None

        for _i in range(0, retries):
            try:
                peripheral = await self._central.connect(connection_string, self)
                break
            except errors.DisconnectionError:
                pass
            except Exception as err:  #pylint:disable=broad-except;We reraise all errors in the handler
                _convert_raise_error(err, 'connect', conn_id)

        if peripheral is None:
            raise DeviceAdapterError(conn_id, 'connect', 'Device found but %d connection attempts failed' % retries)

        self._setup_connection(conn_id, connection_string)
        self._track_property(conn_id, 'peripheral', peripheral)

    async def disconnect(self, conn_id):
        """Asynchronously disconnect from a connected device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
        """

        self._ensure_connection(conn_id, True)
        peripheral = self._get_property(conn_id, 'peripheral')

        try:
            await self._central.disconnect(peripheral)
        except Exception as err:  #pylint:disable=broad-except;We reraise all errors in the handler
            _convert_raise_error(err, 'disconnect', conn_id)
        finally:
            self._teardown_connection(conn_id)

    # Scan Delegate callbacks
    def scan_started(self):
        pass

    def scan_stopped(self):
        pass

    def on_advertisement(self, advert: BLEAdvertisement):
        """Check if the advertisement is from a valid IOTile device and forward if so."""

    # Peripheral Delegate callbacks
    def on_notification(self, peripheral: BLEPeripheral, characteristic: GattCharacteristic, value: bytes):
        pass

    def on_connect(self, peripheral: BLEPeripheral):
        pass

    def on_disconnect(self, peripheral: BLEPeripheral, expected: bool):
        pass


def _convert_raise_error(error, operation, conn_id):
    """This function is only safe to use inside an exception handler."""

    if isinstance(error, (asyncio.TimeoutError, asyncio.CancelledError)):
        raise

    raise DeviceAdapterError(conn_id, operation, 'Unknown error during operation') from error
