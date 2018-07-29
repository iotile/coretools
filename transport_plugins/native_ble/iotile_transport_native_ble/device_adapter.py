# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import datetime
import logging
import threading
import time
import bable_interface
from iotile.core.dev.config import ConfigManager
from iotile.core.hw.reports import IOTileReportParser, IOTileReading, BroadcastReport
from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.utilities.packed import unpack
from iotile.core.exceptions import ArgumentError
from .connection_manager import ConnectionManager
from .tilebus import *

# TODO: release bable interface 1.2.0 (modify READMES...)

# TODO: -> write virtual_adapter
# TODO: clean code + comment
# TODO: write tests
# TODO: test unexpected disconnection

# TODO: ask to Tim how to make send script more async...
# TODO: talk with Tim about unexpected disconnections
# [700313.698910] Bluetooth: hci0: link tx timeout
# [700313.698921] Bluetooth: hci0: killing stalled connection c4:f0:a5:e6:8a:91


class NativeBLEDeviceAdapter(DeviceAdapter):

    def __init__(self, port, on_scan=None, on_disconnect=None, active_scan=None, **kwargs):
        super(NativeBLEDeviceAdapter, self).__init__()

        # Make sure that if someone tries to connect to a device immediately after creating the adapter
        # we tell them we need time to accumulate device advertising packets first
        self.set_config('minimum_scan_time', 2.0)
        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('maximum_connections', 3)

        self.bable = bable_interface.BaBLEInterface()
        self.bable.start(on_error=self._on_ble_error, exit_on_sigint=False)

        if on_scan is not None:
            self.add_callback('on_scan', on_scan)

        if on_disconnect is not None:
            self.add_callback('on_disconnect', on_disconnect)

        if port is None or port == '<auto>':
            controllers = self.find_ble_controllers()
            if len(controllers) > 0:
                self.controller_id = controllers[0].id
            else:
                raise ValueError("Could not find any BLE controller connected to this computer")
        else:
            self.controller_id = int(port)

        self.scanning = False
        self.stopped = False

        if active_scan is not None:
            self._active_scan = active_scan
        else:
            config = ConfigManager()
            self._active_scan = config.get('ble:active-scan')

        self.partial_scan_responses = {}

        # To manage multiple connections
        self.connections = ConnectionManager(self.id)
        self.connections.start()

        self.notification_callbacks_lock = threading.Lock()
        self.notification_callbacks = {}

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        try:
            self._initialize_system_sync()
            self.start_scan(active=self._active_scan)
        except Exception:
            self.stop_sync()
            raise

    def find_ble_controllers(self):
        controllers = self.bable.list_controllers()
        return [ctrl for ctrl in controllers if ctrl.powered and ctrl.low_energy]

    def can_connect(self):
        connections = self.connections.get_connections()
        return len(connections) < int(self.get_config('maximum_connections'))

    def _on_ble_error(self, status, message):
        self._logger.error("BLE error (status=%s, message=%s)", status, message)

    def start_scan(self, active):
        self.bable.start_scan(self._on_device_found, active_scan=active, controller_id=self.controller_id, sync=True)
        self.scanning = True

    def stop_scan(self):
        try:
            self.bable.stop_scan(controller_id=self.controller_id, sync=True)
        except bable_interface.BaBLEException:
            # If we errored our it is because we were not currently scanning, so make sure
            # we update our self.scanning flag (which would not be updated by stop_scan since
            # it raised an exception.)
            pass

        self.scanning = False

    def stop_sync(self):
        if self.scanning:
            self.stop_scan()

        for connection_id in list(self.connections.get_connections()):
            self.disconnect_sync(connection_id)

        self.bable.stop()
        self.connections.stop()

        self.stopped = True

    def _on_device_found(self, success, device, failure_reason):
        if not success:
            self._logger.error("on_device_found() callback called with error: ", failure_reason)
            return

        # If it is an advertisement response
        if device['type'] in [0x00, 0x01, 0x02]:
            if device['uuid'] == TileBusService:
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
                    'connection_string': '{},{}'.format(device['address'], device['address_type']),
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

    def _initialize_system_sync(self):
        connected_devices = self.bable.list_connected_devices(controller_id=self.controller_id)
        for device in connected_devices:
            context = {
                'connection_id': len(self.connections.get_connections()),
                'connection_handle': device.connection_handle,
                'connection_string': device.address
            }
            self.connections.add_connection(context['connection_id'], device.address, context)
            self.disconnect_sync(0)

        # If the dongle was previously left in a dirty state while still scanning, it will
        # not allow new scans to be started. So, forcibly stop any in progress scans.
        # This throws a hardware error if scanning is not in progress which should be ignored.

        self.stop_scan()

        try:
            self.bable.set_advertising(enabled=False)
        except bable_interface.BaBLEException:
            # If advertising is already disabled
            pass

    def connect_async(self, connection_id, connection_string, callback, retries=4, context=None):
        if context is None:
            context = {
                'connection_id': connection_id,
                'retries': retries,
                'retry_connect': False,
                'connection_string': connection_string,
                'connect_time': time.time(),
                'callback': callback
            }

            self.connections.begin_connection(
                connection_id,
                connection_string,
                callback,
                context,
                self.get_config('default_timeout')
            )

        # Don't scan while we attempt to connect to this device
        if self.scanning:
            self.stop_scan()

        address, address_type = connection_string.split(',')

        self.bable.connect(
            address=address,
            address_type=address_type,
            controller_id=self.controller_id,
            on_connected=[self._on_connection_finished, context],
            on_disconnected=[self._on_unexpected_disconnection, context]
        )

    def _on_connection_finished(self, success, result, failure_reason, context):
        """ Called from another thread. Must be not blocking. """

        connection_id = context['connection_id']

        if not success:
            self._logger.error("Error while connecting to the device err=%s", failure_reason)

            # If connection failed to be established, we just should retry to connect
            if failure_reason.packet.native_class == 'HCI' and failure_reason.packet.native_status == 0x3e:
                context['retry_connect'] = True

            self._on_connection_failed(connection_id, self.id, success, failure_reason)
            return

        context['connection_handle'] = result['connection_handle']

        self.bable.probe_services(
            connection_handle=context['connection_handle'],
            controller_id=self.controller_id,
            on_services_probed=[self._on_services_probed, context]
        )

    def _on_services_probed(self, success, result, failure_reason, context):
        connection_id = context['connection_id']

        if not success:
            self._logger.error("Error while probing services to the device, err=%s", failure_reason)
            context['failure_reason'] = "Error while probing services"
            self.disconnect_async(connection_id, self._on_connection_failed)
            return

        services = self._parse_gatt_services(result['services'])

        # Validate that this is a proper IOTile device
        if TileBusService not in services:
            context['failure_reason'] = 'TileBus service not present in GATT services'
            self.disconnect_async(connection_id, self._on_connection_failed)
            return

        context['services'] = services
        tilebus_service = services[TileBusService]

        self.bable.probe_characteristics(
            connection_handle=context['connection_handle'],
            controller_id=self.controller_id,
            start_handle=tilebus_service['service'].handle,
            end_handle=tilebus_service['service'].group_end_handle,
            on_characteristics_probed=[self._on_characteristics_probed, context, tilebus_service]
        )

    def _on_characteristics_probed(self, success, result, failure_reason, context, tilebus_service):
        connection_id = context['connection_id']

        if not success:
            self._logger.error("Error while probing characteristics to the device, err=%s", failure_reason)
            context['failure_reason'] = "Error while probing characteristics"
            self.disconnect_async(connection_id, self._on_connection_failed)
            return

        tilebus_service['characteristics'] = self._parse_gatt_characteristics(tilebus_service['service'],
                                                                              result['characteristics'])

        total_time = time.time() - context['connect_time']
        self._logger.info("Total time to connect to device: %.3f", total_time)

        self.connections.finish_connection(
            connection_id,
            success,
            failure_reason
        )

    def _parse_gatt_services(self, services):
        result = {}
        for service in services:
            result[service.uuid] = {'service': service, 'characteristics': {}}

        return result

    def _parse_gatt_characteristics(self, service, characteristics):
        result = {}
        for characteristic in characteristics:
            if service.handle < characteristic.handle < service.group_end_handle:
                result[characteristic.uuid] = characteristic

        return result

    def _on_report(self, report, connection_id):
        self._logger.info('Received report: %s', str(report))
        self._trigger_callback('on_report', connection_id, report)

        return False

    def _on_report_error(self, code, message, connection_id):
        self._logger.critical(
            "Error receiving reports, no more reports will be processed on this adapter, code=%d, msg=%s", code, message
        )

    def disconnect_async(self, connection_id, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_disconnection(connection_id, callback, self.get_config('default_timeout'))

        self.bable.disconnect(
            connection_handle=context['connection_handle'],
            on_disconnected=[self._on_disconnection_finished, context],
            controller_id=self.controller_id
        )

    def _on_unexpected_disconnection(self, success, result, failure_reason, context):
        connection_id = context['connection_id']

        self._logger.warn('Unexpected disconnection event, handle=%d, reason=0x%X, state=%s',
                          result['connection_handle'],
                          result['code'],
                          self.connections.get_state(connection_id))

        self.connections.unexpected_disconnect(connection_id)
        self._trigger_callback('on_disconnect', self.id, connection_id)

    def _on_disconnection_finished(self, success, result, failure_reason, context):
        if 'connection_handle' in context:
            with self.notification_callbacks_lock:
                for connection_handle, attribute_handle in list(self.notification_callbacks.keys()):
                    if connection_handle == context['connection_handle']:
                        del self.notification_callbacks[(connection_handle, attribute_handle)]

        self.connections.finish_disconnection(
            context['connection_id'],
            success,
            failure_reason
        )

    def _on_connection_failed(self, connection_id, adapter_id, success, failure_reason):
        self._logger.info("_on_connection_failed conn_id=%d, reason=%s", connection_id, failure_reason)

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            self._logger.info("Unable to obtain connection data on unknown connection %d", connection_id)
            context = {}

        self.bable.cancel_connection(controller_id=self.controller_id, sync=False)

        if context.get('retry_connect') and context.get('retries') > 0:
            context['retries'] -= 1
            self.connect_async(
                connection_id,
                context['connection_string'],
                context['callback'],
                context['retries'],
                context
            )
        else:
            self.connections.finish_connection(
                connection_id,
                False,
                context.get('failure_reason', failure_reason)
            )

    def _open_rpc_interface(self, connection_id, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            characteristics = context['services'][TileBusService]['characteristics']
            header_characteristic = characteristics[TileBusReceiveHeaderCharacteristic]
            payload_characteristic = characteristics[TileBusReceivePayloadCharacteristic]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristics to open rpc interface")
            return

        self.bable.set_notification(
            enabled=True,
            connection_handle=context['connection_handle'],
            characteristic=header_characteristic,
            on_notification_set=[self._on_interface_opened, context, payload_characteristic],
            on_notification_received=self._on_notification_received,
            controller_id=self.controller_id,
            timeout=1.0,
            sync=False
        )

    def _open_script_interface(self, connection_id, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        success = TileBusHighSpeedCharacteristic in context['services'][TileBusService]['characteristics']
        reason = None
        if not success:
            reason = 'Could not find high speed streaming characteristic'

        callback(connection_id, self.id, success, reason)

    def _open_streaming_interface(self, connection_id, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self._logger.info("Attempting to enable streaming")
        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            characteristic = context['services'][TileBusService]['characteristics'][TileBusStreamingCharacteristic]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristic to open streaming interface")
            return

        parser = IOTileReportParser(report_callback=self._on_report, error_callback=self._on_report_error)
        parser.context = connection_id

        def on_report_chunk_received(report_chunk):
            parser.add_data(report_chunk)

        self._register_notification_callback(
            context['connection_handle'],
            characteristic.value_handle,
            on_report_chunk_received
        )

        self.bable.set_notification(
            enabled=True,
            connection_handle=context['connection_handle'],
            characteristic=characteristic,
            on_notification_set=[self._on_interface_opened, context],
            on_notification_received=self._on_notification_received,
            controller_id=self.controller_id,
            timeout=1.0,
            sync=False
        )

    def _open_tracing_interface(self, connection_id, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self._logger.info("Attempting to enable tracing")
        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            characteristic = context['services'][TileBusService]['characteristics'][TileBusTracingCharacteristic]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristic to open tracing interface")
            return

        self._register_notification_callback(
            context['connection_handle'],
            characteristic.value_handle,
            lambda trace_chunk: self._trigger_callback('on_trace', connection_id, bytearray(trace_chunk))
        )

        self.bable.set_notification(
            enabled=True,
            connection_handle=context['connection_handle'],
            characteristic=characteristic,
            on_notification_set=[self._on_interface_opened, context],
            on_notification_received=self._on_notification_received,
            controller_id=self.controller_id,
            timeout=1.0,
            sync=False
        )

    def _on_interface_opened(self, success, result, failure_reason, context, next_characteristic=None):
        if not success:
            self.connections.finish_operation(context['connection_id'], False, failure_reason)
            return

        if next_characteristic is not None:
            self.bable.set_notification(
                enabled=True,
                connection_handle=context['connection_handle'],
                characteristic=next_characteristic,
                on_notification_set=[self._on_interface_opened, context],
                on_notification_received=self._on_notification_received,
                controller_id=self.controller_id,
                timeout=1.0,
                sync=False
            )
        else:
            self.connections.finish_operation(context['connection_id'], True, None)

    def _close_rpc_interface(self, connection_id, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'close_interface', callback, self.get_config('default_timeout'))

        try:
            characteristics = context['services'][TileBusService]['characteristics']
            header_characteristic = characteristics[TileBusReceiveHeaderCharacteristic]
            payload_characteristic = characteristics[TileBusReceivePayloadCharacteristic]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristics to open rpc interface")
            return

        self.bable.set_notification(
            enabled=False,
            connection_handle=context['connection_handle'],
            characteristic=header_characteristic,
            on_notification_set=[self._on_interface_closed, context, payload_characteristic],
            controller_id=self.controller_id,
            timeout=1.0
        )

    def _on_interface_closed(self, success, result, failure_reason, context, next_characteristic=None):
        if not success:
            self.connections.finish_operation(context['connection_id'], False, failure_reason)
            return

        if next_characteristic is not None:
            self.bable.set_notification(
                enabled=False,
                connection_handle=context['connection_handle'],
                characteristic=next_characteristic,
                on_notification_set=[self._on_interface_closed, context],
                controller_id=self.controller_id,
                timeout=1.0,
                sync=False
            )
        else:
            self.connections.finish_operation(context['connection_id'], True, None)

    def send_rpc_async(self, connection_id, address, rpc_id, payload, timeout, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'rpc', callback, timeout)

        try:
            characteristics = context['services'][TileBusService]['characteristics']
            send_header_characteristic = characteristics[TileBusSendHeaderCharacteristic]
            send_payload_characteristic = characteristics[TileBusSendPayloadCharacteristic]
            receive_header_characteristic = characteristics[TileBusReceiveHeaderCharacteristic]
            receive_payload_characteristic = characteristics[TileBusReceivePayloadCharacteristic]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristics to open rpc interface")
            return

        length = len(payload)

        if len(payload) < 20:
            payload += b'\x00'*(20 - len(payload))

        if len(payload) > 20:
            self.connections.finish_operation(connection_id, False, "Payload is too long, must be at most 20 bytes")
            return

        header = bytearray([length, 0, rpc_id & 0xFF, (rpc_id >> 8) & 0xFF, address])

        result = {}

        def on_header_received(value):
            result['status'] = value[0]
            result['length'] = value[3]

            if result['length'] > 0:
                self._register_notification_callback(
                    context['connection_handle'],
                    receive_payload_characteristic.value_handle,
                    on_payload_received,
                    once=True
                )
            else:
                result['payload'] = b'\x00'*20
                self.connections.finish_operation(
                    connection_id,
                    True,
                    None,
                    result['status'],
                    result['payload']
                )

        def on_payload_received(value):
            result['payload'] = value[:result['length']]
            self.connections.finish_operation(
                connection_id,
                True,
                None,
                result['status'],
                result['payload']
            )

        self._register_notification_callback(
            context['connection_handle'],
            receive_header_characteristic.value_handle,
            on_header_received,
            once=True
        )

        if length > 0:
            self.bable.write_without_response(
                connection_handle=context['connection_handle'],
                attribute_handle=send_payload_characteristic.value_handle,
                value=bytes(payload),
                controller_id=self.controller_id
            )

        self.bable.write_without_response(
            connection_handle=context['connection_handle'],
            attribute_handle=send_header_characteristic.value_handle,
            value=bytes(header),
            controller_id=self.controller_id
        )

    def send_script_async(self, connection_id, data, progress_callback, callback):
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'script', callback, self.get_config('default_timeout'))
        mtu = int(self.get_config('mtu', 20))  # Split script payloads larger than this

        high_speed_char = context['services'][TileBusService]['characteristics'][TileBusHighSpeedCharacteristic]

        # Count number of chunks to send
        nb_chunks = 1
        if len(data) > mtu:
            nb_chunks = len(data) // mtu
            if len(data) % mtu != 0:
                nb_chunks += 1

        for i in range(0, nb_chunks):
            start = i * mtu
            chunk = data[start: start + mtu]
            sent = False

            while not sent:
                try:
                    self.bable.write_without_response(
                        connection_handle=context['connection_handle'],
                        attribute_handle=high_speed_char.value_handle,
                        value=bytes(chunk),
                        controller_id=self.controller_id
                    )
                    sent = True
                except bable_interface.BaBLEException as err:
                    if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                        time.sleep(0.1)
                    else:
                        raise err

            progress_callback(i, nb_chunks)

        self.connections.finish_operation(connection_id, True, None)

    def _register_notification_callback(self, connection_handle, attribute_handle, callback, once=False):
        notification_id = (connection_handle, attribute_handle)
        with self.notification_callbacks_lock:
            self.notification_callbacks[notification_id] = (callback, once)

    def _on_notification_received(self, success, result, failure_reason):
        if not success:
            self._logger.info("Notification received with failure failure_reason=%s", failure_reason)

        notification_id = (result['connection_handle'], result['attribute_handle'])

        callback = None
        with self.notification_callbacks_lock:
            if notification_id in self.notification_callbacks:
                callback, once = self.notification_callbacks[notification_id]

                if once:
                    del self.notification_callbacks[notification_id]

        if callback is not None:
            callback(result['value'])

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter, should be called every second. """

        if self.stopped:
            return

        # Check if we should start scanning again
        if not self.scanning and len(self.connections.get_connections()) == 0:
            self._logger.info("Restarting scan for devices")
            self.start_scan(self._active_scan)
            self._logger.info("Finished restarting scan for devices")
