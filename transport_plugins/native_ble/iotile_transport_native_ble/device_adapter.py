# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import datetime
import logging
import bable_interface
from iotile.core.dev.config import ConfigManager
from iotile.core.hw.reports import IOTileReading, BroadcastReport
from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.utilities.packed import unpack
from .tilebus import *


class NativeBLEDeviceAdapter(DeviceAdapter):

    def __init__(self, port, on_scan=None, on_disconnect=None, active_scan=None, **kwargs):
        super(NativeBLEDeviceAdapter, self).__init__()

        # Make sure that if someone tries to connect to a device immediately after creating the adapter
        # we tell them we need time to accumulate device advertising packets first
        self.set_config('minimum_scan_time', 2.0)
        self.set_config('expiration_time', 60.0)

        self.bable = bable_interface.BaBLEInterface()
        self.bable.start(self._on_ble_error)

        if on_scan is not None:
            self.add_callback('on_scan', on_scan)

        if on_disconnect is not None:
            self.add_callback('on_disconnect', on_disconnect)

        if port is None or port == '<auto>':
            controllers = [ctrl for ctrl in self.bable.list_controllers() if ctrl.powered and ctrl.low_energy]
            if len(controllers) > 0:
                self.controller_id = controllers[0].id
            else:
                raise ValueError("Could not find any BLE controller connected to this computer")
        else:
            self.controller_id = port

        self.scanning = False
        self.stopped = False

        if active_scan is not None:
            self._active_scan = active_scan
        else:
            config = ConfigManager()
            self._active_scan = config.get('ble:active-scan')

        self.partial_scan_responses = {}

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        try:
            self.start_scan(active=self._active_scan)
        except Exception:
            self.stop_sync()
            raise

    def _on_ble_error(self, status, message):
        self._logger.error("BLE error (status=%s, message=%s)", status, message)

    def start_scan(self, active):
        self.bable.start_scan(self.on_device_found, active_scan=active, controller_id=self.controller_id, sync=True)
        self.scanning = True

    def stop_scan(self):
        self.bable.stop_scan(controller_id=self.controller_id, sync=True)
        self.scanning = False

    def stop_sync(self):
        if self.scanning:
            self.stop_scan()

        self.bable.stop()

        self.stopped = True

    def on_device_found(self, success, device, failure_reason):
        if not success:
            self._logger.error("on_device_found() callback called with error: ", failure_reason)
            return

        # If it is an advertisement response
        if device['type'] == 0x00:  # TODO: ask for type == 0x06 ? BLED112 only ?
            raw_uuid = device['uuid'].decode('hex')

            if len(raw_uuid) != 16:
                return

            service = uuid.UUID(bytes_le=raw_uuid)

            if service == TileBusService:
                if len(device['manufacturer_data']) != 6:
                    self._logger.error("Received advertisement response with wrong manufacturer data length "
                                       "(expected=6, received=%d)", len(device['manufacturer_data']))
                    return

                device_uuid, flags = unpack("<LH", device['manufacturer_data'])

                pending = bool(flags & (1 << 0))
                low_voltage = bool(flags & (1 << 1))
                user_connected = bool(flags & (1 << 2))

                info = {
                    'user_connected': user_connected,
                    'connection_string': device['address'],
                    'uuid': device_uuid,
                    'pending_data': pending,
                    'low_voltage': low_voltage,
                    'signal_strength': device['rssi']
                }

                if not self._active_scan:
                    self._trigger_callback('on_scan', self.id, info, self.get_config('expiration_time'))
                else:
                    self.partial_scan_responses[device['address']] = info

        # If it is a scan response
        elif device['type'] == 0x04 and device['address'] in self.partial_scan_responses:
            if len(device['manufacturer_data']) != 16:
                self._logger.error("Received scan response with wrong manufacturer data length "
                                   "(expected=16, received=%d)", len(device['manufacturer_data']))
                return

            voltage, stream, reading, reading_time, curr_time = unpack("<HHLLL", device['manufacturer_data'])

            info = self.partial_scan_responses[device['address']]
            info['voltage'] = voltage / 256.0
            info['current_time'] = curr_time
            info['last_seen'] = datetime.datetime.now()

            # If there is a valid reading on the advertising data, broadcast it
            if stream != 0xFFFF:
                reading = IOTileReading(reading_time, stream, reading, reading_time=datetime.datetime.utcnow())
                report = BroadcastReport.FromReadings(info['uuid'], [reading], curr_time)
                self._trigger_callback('on_report', None, report)

            del self.partial_scan_responses[device['address']]
            self._trigger_callback('on_scan', self.id, info, self.get_config('expiration_time'))
