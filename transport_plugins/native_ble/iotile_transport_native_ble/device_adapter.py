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
from iotile.core.exceptions import ArgumentError, ExternalError
from .connection_manager import ConnectionManager
from .tilebus import *

# TODO: release bable interface 1.2.0 (modify READMES...)


class NativeBLEDeviceAdapter(DeviceAdapter):
    """Device adapter for native BLE controllers, supporting multiple simultaneous connections."""

    def __init__(self, port, on_scan=None, on_disconnect=None, active_scan=None, **kwargs):
        super(NativeBLEDeviceAdapter, self).__init__()

        # Create logger
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        # Register configuration
        self.set_config('minimum_scan_time', 2.0)  # Time to accumulate device advertising packets first
        self.set_config('default_timeout', 10.0)  # Time before timeout an operation
        self.set_config('expiration_time', 60.0)  # Time before a scanned device expired
        self.set_config('maximum_connections', 3)  # Maximum number of simultaneous connections per controller

        # Create the baBLE interface to interact with BLE controllers
        self.bable = bable_interface.BaBLEInterface()

        # Get the list of BLE controllers
        self.bable.start(on_error=self._on_ble_error)
        controllers = self._find_ble_controllers()
        self.bable.stop()

        if len(controllers) == 0:
            raise ExternalError("Could not find any BLE controller connected to this computer")

        # Parse port and check if it exists
        if port is None or port == '<auto>':
            self.controller_id = controllers[0].id
        else:
            self.controller_id = int(port)
            if not any(controller.id == self.controller_id for controller in controllers):
                raise ExternalError("Could not find a BLE controller with the given ID, controller_id=%s"
                                    .format(self.controller_id))

        # Restart baBLE with the selected controller id to prevent conflicts if multiple controllers
        self.bable.start(on_error=self._on_ble_error, exit_on_sigint=False, controller_id=self.controller_id)

        # Register callbacks
        if on_scan is not None:
            self.add_callback('on_scan', on_scan)
        if on_disconnect is not None:
            self.add_callback('on_disconnect', on_disconnect)

        self.scanning = False
        self.stopped = False

        if active_scan is not None:
            self._active_scan = active_scan
        else:
            config = ConfigManager()
            self._active_scan = config.get('ble:active-scan')

        # To register advertising packets waiting for a scan response (only if active scan)
        self.partial_scan_responses = {}

        # To manage multiple connections
        self.connections = ConnectionManager(self.id)
        self.connections.start()

        # Notification callbacks
        self.notification_callbacks_lock = threading.Lock()
        self.notification_callbacks = {}

        try:
            self._initialize_system_sync()
            self.start_scan(active=self._active_scan)
        except Exception:
            self.stop_sync()
            raise

    def _find_ble_controllers(self):
        """Get a list of the available and powered BLE controllers"""
        controllers = self.bable.list_controllers()
        return [ctrl for ctrl in controllers if ctrl.powered and ctrl.low_energy]

    def _on_ble_error(self, status, message):
        """Callback function called when a BLE error, not related to a request, is received. Just log it for now."""
        self._logger.error("BLE error (status=%s, message=%s)", status, message)

    def _initialize_system_sync(self):
        """Initialize the device adapter by removing all active connections and resetting scan and advertising to have
        a clean starting state."""
        connected_devices = self.bable.list_connected_devices()
        for device in connected_devices:
            context = {
                'connection_id': len(self.connections.get_connections()),
                'connection_handle': device.connection_handle,
                'connection_string': device.address
            }
            self.connections.add_connection(context['connection_id'], device.address, context)
            self.disconnect_sync(context['connection_id'])

        self.stop_scan()

        try:
            self.bable.set_advertising(enabled=False)
        except bable_interface.BaBLEException:
            # If advertising is already disabled
            pass

    def can_connect(self):
        """Check if this adapter can take another connection

        Returns:
            bool: whether there is room for one more connection
        """
        return len(self.connections.get_connections()) < int(self.get_config('maximum_connections'))

    def start_scan(self, active):
        """Start a scan. Will call self._on_device_found for each device scanned.
        Args:
            active (bool): Indicate if it is an active scan (probing for scan response) or not.
        """
        try:
            self.bable.start_scan(self._on_device_found, active_scan=active, sync=True)
        except bable_interface.BaBLEException as err:
            # If we are already scanning, raise an error only we tried to change the active scan param
            if self._active_scan != active:
                raise err

        self._active_scan = active
        self.scanning = True

    def _on_device_found(self, success, device, failure_reason):
        """Callback function called when a device has been scanned.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            device (dict): The scanned device information
              - type (int): Indicates if it is an advertising report or a scan response
              - uuid (uuid.UUID): The service uuid
              - manufacturer_data (bytes): The manufacturer data
              - address (str): The device BT address
              - address_type (str): The device address type (either 'random' or 'public')
              - rssi (int): The signal strength
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
        """
        if not success:
            self._logger.error("on_device_found() callback called with error: ", failure_reason)
            return

        # If it is an adverting report
        if device['type'] in [0x00, 0x01, 0x02]:
            # If it has the TileBusService
            if device['uuid'] == TileBusService.uuid:
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
                    # If scan is not active, we won't receive a scan response so we trigger the `on_scan` callback
                    self._trigger_callback('on_scan', self.id, info, self.get_config('expiration_time'))
                else:
                    # Else we register the information to get them on scan response received
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

    def stop_scan(self):
        """Stop to scan."""
        try:
            self.bable.stop_scan(sync=True)
        except bable_interface.BaBLEException:
            # If we errored our it is because we were not currently scanning
            pass

        self.scanning = False

    def connect_async(self, connection_id, connection_string, callback, retries=4, context=None):
        """Connect to a device by its connection_string

        This function asynchronously connects to a device by its BLE address + address type passed in the
        connection_string parameter and calls callback when finished. Callback is called on either success
        or failure with the signature:
            callback(connection_id: int, result: bool, value: None)
        The optional retries argument specifies how many times we should retry the connection
        if the connection fails due to an early disconnect.  Early disconnects are expected ble failure
        modes in busy environments where the slave device misses the connection packet and the master
        therefore fails immediately. Retrying a few times should succeed in this case.

        Args:
            connection_string (string): A BLE address information in AA:BB:CC:DD:EE:FF,<address_type> format
            connection_id (int): A unique integer set by the caller for referring to this connection once created
            callback (callable): A callback function called when the connection has succeeded or failed
            retries (int): The number of attempts to connect to this device that can end in early disconnect
                before we give up and report that we could not connect. A retry count of 0 will mean that
                we fail as soon as we receive the first early disconnect.
            context (dict): If we are retrying to connect, passes the context to not considering it as a new connection.
        """
        if context is None:
            # It is the first attempt to connect: begin a new connection
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

        # First, cancel any pending connection to prevent errors when starting a new one
        self.bable.cancel_connection(sync=False)

        # Send a connect request
        self.bable.connect(
            address=address,
            address_type=address_type,
            connection_interval=[7.5, 7.5],
            on_connected=[self._on_connection_finished, context],
            on_disconnected=[self._on_unexpected_disconnection, context]
        )

    def _on_connection_finished(self, success, result, failure_reason, context):
        """Callback called when the connection attempt to a BLE device has finished.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): The connection information (if successful)
              - connection_handle (int): The connection handle
              - address (str): The device BT address
              - address_type (str): The device address type (either 'random' or 'public')
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
        """
        connection_id = context['connection_id']

        if not success:
            self._logger.error("Error while connecting to the device err=%s", failure_reason)

            # If connection failed to be established, we just should retry to connect
            if failure_reason.packet.native_class == 'HCI' and failure_reason.packet.native_status == 0x3e:
                context['retry_connect'] = True

            self._on_connection_failed(connection_id, self.id, success, failure_reason)
            return

        context['connection_handle'] = result['connection_handle']

        # After connection has been done, probe GATT services
        self.bable.probe_services(
            connection_handle=context['connection_handle'],
            on_services_probed=[self._on_services_probed, context]
        )

    def _on_services_probed(self, success, result, failure_reason, context):
        """Callback called when the services has been probed.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): Information probed (if successful)
              - services (list): The list of services probed (bable_interface.Service instances)
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
        """
        connection_id = context['connection_id']

        if not success:
            self._logger.error("Error while probing services to the device, err=%s", failure_reason)
            context['failure_reason'] = "Error while probing services"
            self.disconnect_async(connection_id, self._on_connection_failed)
            return

        services = {service: {} for service in result['services']}

        # Validate that this is a proper IOTile device
        if TileBusService not in services:
            context['failure_reason'] = 'TileBus service not present in GATT services'
            self.disconnect_async(connection_id, self._on_connection_failed)
            return

        context['services'] = services

        # Finally, probe GATT characteristics
        self.bable.probe_characteristics(
            connection_handle=context['connection_handle'],
            start_handle=TileBusService.handle,
            end_handle=TileBusService.group_end_handle,
            on_characteristics_probed=[self._on_characteristics_probed, context]
        )

    def _on_characteristics_probed(self, success, result, failure_reason, context):
        """Callback called when the characteristics has been probed.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): Information probed (if successful)
              - characteristics (list): The list of characteristics probed (bable_interface.Characteristic instances)
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
        """
        connection_id = context['connection_id']

        if not success:
            self._logger.error("Error while probing characteristics to the device, err=%s", failure_reason)
            context['failure_reason'] = "Error while probing characteristics"
            self.disconnect_async(connection_id, self._on_connection_failed)
            return

        context['services'][TileBusService] = {
            characteristic: characteristic for characteristic in result['characteristics']
        }

        total_time = time.time() - context['connect_time']
        self._logger.info("Total time to connect to device: %.3f", total_time)

        self.connections.finish_connection(
            connection_id,
            success,
            failure_reason
        )

    def _on_connection_failed(self, connection_id, adapter_id, success, failure_reason):
        """Callback function called when a connection has failed.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            connection_id (int): A unique identifier for this connection on the DeviceManager that owns this adapter.
            adapter_id (int): A unique identifier for the DeviceManager
            success (bool): A bool indicating that the operation is successful or not
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
        """
        self._logger.info("_on_connection_failed connection_id=%d, reason=%s", connection_id, failure_reason)

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            self._logger.info("Unable to obtain connection data on unknown connection %d", connection_id)
            context = {}

        # Cancel the connection to be able to resend a connect request later (else the controller sends an error)
        self.bable.cancel_connection(sync=False)

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

    def disconnect_async(self, connection_id, callback):
        """Asynchronously disconnect from a device that has previously been connected

        Args:
            connection_id (int): A unique identifier for this connection on the DeviceManager that owns this adapter.
            callback (callable): A function called as callback(connection_id, adapter_id, success, failure_reason)
            when the disconnection finishes. Disconnection can only either succeed or timeout.
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_disconnection(connection_id, callback, self.get_config('default_timeout'))

        self.bable.disconnect(
            connection_handle=context['connection_handle'],
            on_disconnected=[self._on_disconnection_finished, context]
        )

    def _on_unexpected_disconnection(self, success, result, failure_reason, context):
        """Callback function called when an unexpected disconnection occured (meaning that we didn't previously send
        a `disconnect` request).
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): Disconnection information (if successful)
              - connection_handle (int): The connection handle that just disconnected
              - code (int): The reason code
              - reason (str): A message explaining the reason code in plain text
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
            context (dict): The connection context
        """
        connection_id = context['connection_id']

        self._logger.warn('Unexpected disconnection event, handle=%d, reason=0x%X, state=%s',
                          result['connection_handle'],
                          result['code'],
                          self.connections.get_state(connection_id))

        self.connections.unexpected_disconnect(connection_id)
        self._trigger_callback('on_disconnect', self.id, connection_id)

    def _on_disconnection_finished(self, success, result, failure_reason, context):
        """Callback function called when a previously asked disconnection has been finished.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): Disconnection information (if successful)
              - connection_handle (int): The connection handle that just disconnected
              - code (int): The reason code
              - reason (str): A message explaining the reason code in plain text
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
            context (dict): The connection context
        """
        if 'connection_handle' in context:
            # Remove all the notification callbacks registered for this connection
            with self.notification_callbacks_lock:
                for connection_handle, attribute_handle in list(self.notification_callbacks.keys()):
                    if connection_handle == context['connection_handle']:
                        del self.notification_callbacks[(connection_handle, attribute_handle)]

        self.connections.finish_disconnection(
            context['connection_id'],
            success,
            failure_reason
        )

    def _open_rpc_interface(self, connection_id, callback):
        """Enable RPC interface for this IOTile device

        Args:
            connection_id (int): The unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            service = context['services'][TileBusService]
            header_characteristic = service[ReceiveHeaderChar]
            payload_characteristic = service[ReceivePayloadChar]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristics to open rpc interface")
            return

        # Enable notification from ReceiveHeaderChar characteristic (ReceivePayloadChar will be enable just after)
        self.bable.set_notification(
            enabled=True,
            connection_handle=context['connection_handle'],
            characteristic=header_characteristic,
            on_notification_set=[self._on_interface_opened, context, payload_characteristic],
            on_notification_received=self._on_notification_received,
            sync=False
        )

    def _open_script_interface(self, connection_id, callback):
        """Enable script streaming interface for this IOTile device

        Args:
            connection_id (int): The unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        success = HighSpeedChar in context['services'][TileBusService]
        reason = None
        if not success:
            reason = 'Could not find high speed streaming characteristic'

        callback(connection_id, self.id, success, reason)

    def _open_streaming_interface(self, connection_id, callback):
        """Enable streaming interface for this IOTile device

        Args:
            connection_id (int): The unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self._logger.info("Attempting to enable streaming")
        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            characteristic = context['services'][TileBusService][StreamingChar]
        except KeyError:
            self.connections.finish_operation(
                connection_id,
                False,
                "Can't find characteristic to open streaming interface"
            )
            return

        context['parser'] = IOTileReportParser(report_callback=self._on_report, error_callback=self._on_report_error)
        context['parser'].context = connection_id

        def on_report_chunk_received(report_chunk):
            """Callback function called when a report chunk has been received."""
            context['parser'].add_data(report_chunk)

        # Register our callback function in the notifications callbacks
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
            timeout=1.0,
            sync=False
        )

    def _open_tracing_interface(self, connection_id, callback):
        """Enable the tracing interface for this IOTile device

        Args:
            connection_id (int): The unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self._logger.info("Attempting to enable tracing")
        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            characteristic = context['services'][TileBusService][TracingChar]
        except KeyError:
            self.connections.finish_operation(
                connection_id,
                False,
                "Can't find characteristic to open tracing interface"
            )
            return

        # Register a callback function in the notifications callbacks, to trigger `on_trace` callback when a trace is
        # notified.
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
            timeout=1.0,
            sync=False
        )

    def _on_interface_opened(self, success, result, failure_reason, context, next_characteristic=None):
        """Callback function called when the notification related to an interface has been enabled.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): Information (if successful)
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
            context (dict): The connection context
            next_characteristic (bable_interface.Characteristic): If not None, indicate another characteristic to enable
                notification.
        """
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
                sync=False
            )
        else:
            self.connections.finish_operation(context['connection_id'], True, None)

    def _close_rpc_interface(self, connection_id, callback):
        """Disable RPC interface for this IOTile device

        Args:
            connection_id (int): The unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'close_interface', callback, self.get_config('default_timeout'))

        try:
            service = context['services'][TileBusService]
            header_characteristic = service[ReceiveHeaderChar]
            payload_characteristic = service[ReceivePayloadChar]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristics to open rpc interface")
            return

        self.bable.set_notification(
            enabled=False,
            connection_handle=context['connection_handle'],
            characteristic=header_characteristic,
            on_notification_set=[self._on_interface_closed, context, payload_characteristic],
            timeout=1.0
        )

    def _on_interface_closed(self, success, result, failure_reason, context, next_characteristic=None):
        """Callback function called when the notification related to an interface has been disabled.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): Information (if successful)
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
            context (dict): The connection context
            next_characteristic (bable_interface.Characteristic): If not None, indicate another characteristic to
                disable notification.
        """
        if not success:
            self.connections.finish_operation(context['connection_id'], False, failure_reason)
            return

        if next_characteristic is not None:
            self.bable.set_notification(
                enabled=False,
                connection_handle=context['connection_handle'],
                characteristic=next_characteristic,
                on_notification_set=[self._on_interface_closed, context],
                timeout=1.0,
                sync=False
            )
        else:
            self.connections.finish_operation(context['connection_id'], True, None)

    def _on_report(self, report, connection_id):
        """Callback function called when a report has been processed.

        Args:
            report (IOTileReport): The report object
            connection_id (int): The connection id related to this report

        Returns:
            - True to indicate that IOTileReportParser should also keep a copy of the report
            or False to indicate it should delete it.
        """
        self._logger.info('Received report: %s', str(report))
        self._trigger_callback('on_report', connection_id, report)

        return False

    def _on_report_error(self, code, message, connection_id):
        """Callback function called if an error occured while parsing a report"""
        self._logger.critical(
            "Error receiving reports, no more reports will be processed on this adapter, code=%d, msg=%s", code, message
        )

    def send_rpc_async(self, connection_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            connection_id (int): A unique identifier that will refer to this connection
            address (int): The address of the tile that we wish to send the RPC to
            rpc_id (int): The 16-bit id of the RPC we want to call
            payload (bytearray): The payload of the command
            timeout (float): The number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                    'connection_id': The connection id
                    'adapter_id': This adapter's id
                    'success': A bool indicating whether we received a response to our attempted RPC
                    'failure_reason': A string with the reason for the failure if success == False
                    'status': The one byte status code returned for the RPC if success == True else None
                    'payload': A bytearray with the payload returned by RPC if success == True else None
        """
        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        connection_handle = context['connection_handle']

        self.connections.begin_operation(connection_id, 'rpc', callback, timeout)

        try:
            service = context['services'][TileBusService]
            send_header_characteristic = service[SendHeaderChar]
            send_payload_characteristic = service[SendPayloadChar]
            receive_header_characteristic = service[ReceiveHeaderChar]
            receive_payload_characteristic = service[ReceivePayloadChar]
        except KeyError:
            self.connections.finish_operation(connection_id, False, "Can't find characteristics to open rpc interface")
            return

        length = len(payload)
        if length < 20:
            payload += b'\x00'*(20 - length)
        if length > 20:
            self.connections.finish_operation(connection_id, False, "Payload is too long, must be at most 20 bytes")
            return

        header = bytearray([length, 0, rpc_id & 0xFF, (rpc_id >> 8) & 0xFF, address])
        result = {}

        def on_header_received(value):
            """Callback function called when a notification has been received with the RPC header response."""
            result['status'] = value[0]
            result['length'] = value[3]

            if result['length'] == 0:
                # Simulate a empty payload received to end the RPC response
                self._on_notification_received(True, {
                    'connection_handle': connection_handle,
                    'attribute_handle': receive_payload_characteristic.value_handle,
                    'value': b'\x00'*20
                }, None)

        def on_payload_received(value):
            """Callback function called when a notification has been received with the RPC payload response."""
            result['payload'] = value[:result['length']]
            self.connections.finish_operation(
                connection_id,
                True,
                None,
                result['status'],
                result['payload']
            )

        # Register the header notification callback
        self._register_notification_callback(
            connection_handle,
            receive_header_characteristic.value_handle,
            on_header_received,
            once=True
        )

        # Register the payload notification callback
        self._register_notification_callback(
            connection_handle,
            receive_payload_characteristic.value_handle,
            on_payload_received,
            once=True
        )

        if length > 0:
            # If payload is not empty, send it first
            self.bable.write_without_response(
                connection_handle=connection_handle,
                attribute_handle=send_payload_characteristic.value_handle,
                value=bytes(payload)
            )

        self.bable.write_without_response(
            connection_handle=connection_handle,
            attribute_handle=send_header_characteristic.value_handle,
            value=bytes(header)
        )

    def send_script_async(self, connection_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            connection_id (int): A unique identifier that will refer to this connection
            data (bytes): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script. The callback will be called as
                callback(connection_id, adapter_id, success, failure_reason)
                    'connection_id': the connection id
                    'adapter_id': this adapter's id
                    'success': a bool indicating whether we received a response to our attempted RPC
                    'failure_reason': a string with the reason for the failure if success == False
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'script', callback, self.get_config('default_timeout'))
        mtu = int(self.get_config('mtu', 20))  # Split script payloads larger than this

        high_speed_char = context['services'][TileBusService][HighSpeedChar]

        # Count number of chunks to send
        nb_chunks = 1
        if len(data) > mtu:
            nb_chunks = len(data) // mtu
            if len(data) % mtu != 0:
                nb_chunks += 1

        def send_script():
            """Function sending every chunks of the script. Executed in a separated thread."""
            for i in range(0, nb_chunks):
                start = i * mtu
                chunk = data[start: start + mtu]
                sent = False

                while not sent:
                    try:
                        self.bable.write_without_response(
                            connection_handle=context['connection_handle'],
                            attribute_handle=high_speed_char.value_handle,
                            value=bytes(chunk)
                        )
                        sent = True
                    except bable_interface.BaBLEException as err:
                        if err.packet.status == 'Rejected':  # If we are streaming too fast, back off and try again
                            time.sleep(0.05)
                        else:
                            self.connections.finish_operation(connection_id, False, err.message)
                            return

                progress_callback(i, nb_chunks)

            self.connections.finish_operation(connection_id, True, None)

        # Start the thread to send the script asynchronously
        send_script_thread = threading.Thread(target=send_script, name='SendScriptThread')
        send_script_thread.daemon = True
        send_script_thread.start()

    def _register_notification_callback(self, connection_handle, attribute_handle, callback, once=False):
        """Register a callback as a notification callback. It will be called if a notification with the matching
        connection_handle and attribute_handle is received.

        Args:
            connection_handle (int): The connection handle to watch
            attribute_handle (int): The attribute handle to watch
            callback (func): The callback function to call once the notification has been received
            once (bool): Should the callback only be called once (and then removed from the notification callbacks)
        """
        notification_id = (connection_handle, attribute_handle)
        with self.notification_callbacks_lock:
            self.notification_callbacks[notification_id] = (callback, once)

    def _on_notification_received(self, success, result, failure_reason):
        """Callback function called when a notification has been received.
        It is executed in the baBLE working thread: should not be blocking.

        Args:
            success (bool): A bool indicating that the operation is successful or not
            result (dict): The notification information
              - value (bytes): Data notified
            failure_reason (any): An object indicating the reason why the operation is not successful (else None)
        """
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

    def stop_sync(self):
        """Safely stop this BLED112 instance without leaving it in a weird state"""
        # Stop to scan
        if self.scanning:
            self.stop_scan()

        # Disconnect all connected devices
        for connection_id in list(self.connections.get_connections()):
            self.disconnect_sync(connection_id)

        # Stop the baBLE interface
        self.bable.stop()
        # Stop the connection manager
        self.connections.stop()

        self.stopped = True

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter, should be called every second. """

        if self.stopped:
            return

        # Check if we should start scanning again
        if not self.scanning and len(self.connections.get_connections()) == 0:
            self._logger.info("Restarting scan for devices")
            self.start_scan(self._active_scan)
            self._logger.info("Finished restarting scan for devices")
