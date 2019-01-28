# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from __future__ import unicode_literals, absolute_import, print_function
from queue import Queue
import time
import threading
import logging
import datetime
import copy
from future.utils import viewitems
import serial
import serial.tools.list_ports
from iotile_transport_bled112 import bgapi_structures
from iotile.core.dev.config import ConfigManager
from iotile.core.utilities.packed import unpack
from iotile.core.exceptions import HardwareError
from iotile.core.hw.reports import IOTileReportParser, IOTileReading, BroadcastReport
from iotile.core.hw.transport.adapter import DeviceAdapter
from .bled112_cmd import BLED112CommandProcessor
from .tilebus import TileBusService, TileBusStreamingCharacteristic, TileBusTracingCharacteristic, TileBusHighSpeedCharacteristic
from .async_packet import AsyncPacketBuffer


def packet_length(header):
    """Find the BGAPI packet length given its header"""

    highbits = header[0] & 0b11
    lowbits = header[1]

    return (highbits << 8) | lowbits


class BLED112Adapter(DeviceAdapter):
    """Callback based BLED112 wrapper supporting multiple simultaneous connections.

    Optional Keyword Args:
        stop_check_interval (float): When we close this adapter instance, we need to
            notify our worker thread with a stop signal.  This is the interval at which
            the worker thread checks for the signal.  It defaults to 0.5s but is set to
            a faster value like 10 ms during testing to make tests run faster.  Lower
            values increase CPU usage in production.
    """

    ExpirationTime = 60  # Expire devices 60 seconds after seeing them

    def __init__(self, port, on_scan=None, on_disconnect=None, passive=None, **kwargs):
        super(BLED112Adapter, self).__init__()

        # Get optional configuration flags
        stop_check_interval = kwargs.get('stop_check_interval', 0.1)

        # Make sure that if someone tries to connect to a device immediately after creating the adapter
        # we tell them we need time to accumulate device advertising packets first
        self.set_config('minimum_scan_time', 2.0)

        if on_scan is not None:
            self.add_callback('on_scan', on_scan)

        if on_disconnect is not None:
            self.add_callback('on_disconnect', on_disconnect)

        if port is None or port == '<auto>':
            devices = self.find_bled112_devices()
            if len(devices) > 0:
                port = devices[0]
            else:
                raise ValueError("Could not find any BLED112 adapters connected to this computer")

        self.scanning = False
        self.stopped = False

        config = ConfigManager()

        if passive is not None:
            self._active_scan = not passive
        else:
            self._active_scan = config.get('bled112:active-scan')

        self._throttle_broadcast = config.get('bled112:throttle-broadcast')

        # Prepare internal state of scannable and in progress devices
        # Do this before spinning off the BLED112CommandProcessor
        # in case a scanned device is seen immediately.
        self.partial_scan_responses = {}

        self._broadcast_state = {}
        self._connections = {}

        self.count_lock = threading.Lock()
        self.connecting_count = 0
        self.maximum_connections = 0

        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self._serial_port = serial.Serial(port, 256000, timeout=0.01, rtscts=True)
        self._stream = AsyncPacketBuffer(self._serial_port, header_length=4, length_function=packet_length)
        self._commands = Queue()
        self._command_task = BLED112CommandProcessor(self._stream, self._commands, stop_check_interval=stop_check_interval)
        self._command_task.event_handler = self._handle_event
        self._command_task.start()

        try:
            self.initialize_system_sync()
            self.start_scan(self._active_scan)
        except:
            self.stop_sync()
            raise

    @classmethod
    def find_bled112_devices(cls):
        """Look for BLED112 dongles on this computer and start an instance on each one"""
        found_devs = []

        ports = serial.tools.list_ports.comports()
        for port in ports:
            if not hasattr(port, 'pid') or not hasattr(port, 'vid'):
                continue

            # Check if the device matches the BLED112's PID/VID combination
            if port.pid == 1 and port.vid == 9304:
                found_devs.append(port.device)

        return found_devs

    def can_connect(self):
        """Check if this adapter can take another connection

        Returns:
            bool: whether there is room for one more connection
        """

        return len(self._connections) < self.maximum_connections

    def stop_sync(self):
        """Safely stop this BLED112 instance without leaving it in a weird state"""

        if self.scanning:
            self.stop_scan()

        # Make a copy since this will change size as we disconnect
        con_copy = copy.copy(self._connections)

        for _, context in viewitems(con_copy):
            self.disconnect_sync(context['connection_id'])

        self._command_task.stop()
        self._stream.stop()
        self._serial_port.close()

        self.stopped = True

    def stop_scan(self):
        """Stop the scanning task"""
        self._command_task.sync_command(['_stop_scan'])
        self.scanning = False

    def start_scan(self, active):
        """Start the scanning task"""
        self._command_task.sync_command(['_start_scan', active])
        self.scanning = True

    def connect_async(self, connection_id, connection_string, callback, retries=4):
        """Connect to a device by its connection_string

        This function asynchronously connects to a device by its BLE address passed in the
        connection_string parameter and calls callback when finished.  Callback is called
        on either success or failure with the signature:

        callback(conn_id: int, result: bool, value: None)

        The optional retries argument specifies how many times we should retry the connection
        if the connection fails due to an early disconnect.  Early disconnects are expected ble failure
        modes in busy environments where the slave device misses the connection packet and the master
        therefore fails immediately.  Retrying a few times should succeed in this case.

        Args:
            connection_string (string): A BLE address is XX:YY:ZZ:AA:BB:CC format
            connection_id (int): A unique integer set by the caller for referring to this connection
                once created
            callback (callable): A callback function called when the connection has succeeded or
                failed
            retries (int): The number of attempts to connect to this device that can end in early disconnect
                before we give up and report that we could not connect.  A retry count of 0 will mean that
                we fail as soon as we receive the first early disconnect.
        """
        context = {}
        context['connection_id'] = connection_id
        context['callback'] = callback
        context['retries'] = retries
        context['connection_string'] = connection_string

        # Don't scan while we attempt to connect to this device
        if self.scanning:
            self.stop_scan()

        with self.count_lock:
            self.connecting_count += 1

        self._command_task.async_command(['_connect', connection_string],
                                         self._on_connection_finished, context)

    def disconnect_async(self, conn_id, callback):
        """Asynchronously disconnect from a device that has previously been connected

        Args:
            conn_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): A function called as callback(conn_id, adapter_id, success, failure_reason)
            when the disconnection finishes.  Disconnection can only either succeed or timeout.
        """

        found_handle = None
        # Find the handle by connection id
        for handle, conn in viewitems(self._connections):
            if conn['connection_id'] == conn_id:
                found_handle = handle

        if found_handle is None:
            callback(conn_id, self.id, False, 'Invalid connection_id')
            return

        self._command_task.async_command(['_disconnect', found_handle], self._on_disconnect,
                                         {'connection_id': conn_id, 'handle': found_handle,
                                          'callback': callback})

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        found_handle = None
        # Find the handle by connection id
        for handle, conn in viewitems(self._connections):
            if conn['connection_id'] == conn_id:
                found_handle = handle

        if found_handle is None:
            callback(conn_id, self.id, False, 'Invalid connection_id', None, None)
            return

        services = self._connections[found_handle]['services']

        self._command_task.async_command(['_send_rpc', found_handle, services, address, rpc_id, payload, timeout], self._send_rpc_finished,
                                         {'connection_id': conn_id, 'handle': found_handle,
                                          'callback': callback})

    def send_script_async(self, conn_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (bytes): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        found_handle = None
        # Find the handle by connection id
        for handle, conn in viewitems(self._connections):
            if conn['connection_id'] == conn_id:
                found_handle = handle

        if found_handle is None:
            callback(conn_id, self.id, False, 'Invalid connection_id')
            return

        services = self._connections[found_handle]['services']

        self._command_task.async_command(['_send_script', found_handle, services, data, 0, progress_callback],
                                         self._send_script_finished, {'connection_id': conn_id,
                                                                      'callback': callback})

    def _send_script_finished(self, result):
        success, retval, context = self._parse_return(result)
        callback = context['callback']

        if retval is not None and 'reason' in retval:
            failure = retval['reason']
        else:
            failure = None

        callback(context['connection_id'], self.id, success, failure)

    def _send_rpc_finished(self, result):
        success, retval, context = self._parse_return(result)
        callback = context['callback']

        status = None
        payload = None
        disconnected = False

        if retval is not None and 'reason' in retval:
            failure = retval['reason']
        else:
            failure = None

        if success:
            status = retval['status']

            if status == 0xFF:
                length = 0
            elif status & (1 << 7):
                length = retval['length']
            else:
                length = 0

            payload = retval['payload'][:length]

            disconnected = retval['disconnected']

        if disconnected:
            self._remove_connection(context['handle'])
            self._trigger_callback('on_disconnect', self.id, context['connection_id'])

        callback(context['connection_id'], self.id, success, failure, status, payload)

    def _open_rpc_interface(self, conn_id, callback):
        """Enable RPC interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            handle = self._find_handle(conn_id)
            services = self._connections[handle]['services']
        except (ValueError, KeyError):
            callback(conn_id, self.id, False, 'Connection closed unexpectedly before we could open the rpc interface')
            return

        self._command_task.async_command(['_enable_rpcs', handle, services], self._on_interface_finished, {'connection_id': conn_id, 'callback': callback})

    def _open_script_interface(self, conn_id, callback):
        """Enable script streaming interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            handle = self._find_handle(conn_id)
            services = self._connections[handle]['services']
        except (ValueError, KeyError):
            callback(conn_id, self.id, False, 'Connection closed unexpectedly before we could open the script interface')
            return

        success = TileBusHighSpeedCharacteristic in services[TileBusService]['characteristics']
        reason = None
        if not success:
            reason = 'Could not find high speed streaming characteristic'

        callback(conn_id, self.id, success, reason)

    def _open_streaming_interface(self, conn_id, callback):
        """Enable sensor graph streaming interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            handle = self._find_handle(conn_id)
            services = self._connections[handle]['services']
        except (ValueError, KeyError):
            callback(conn_id, self.id, False, 'Connection closed unexpectedly before we could open the streaming interface')
            return

        self._command_task.async_command(['_enable_streaming', handle, services], self._on_interface_finished,
                                         {'connection_id': conn_id, 'callback': callback})

    def _open_tracing_interface(self, conn_id, callback):
        """Enable the debug tracing interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            handle = self._find_handle(conn_id)
            services = self._connections[handle]['services']
        except (ValueError, KeyError):
            callback(conn_id, self.id, False, 'Connection closed unexpectedly before we could open the streaming interface')
            return

        self._command_task.async_command(['_enable_tracing', handle, services],
                                         self._on_interface_finished, {'connection_id': conn_id, 'callback': callback})

    def _close_rpc_interface(self, conn_id, callback):
        """Disable RPC interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        try:
            handle = self._find_handle(conn_id)
            services = self._connections[handle]['services']
        except (ValueError, KeyError):
            callback(conn_id, self.id, False, 'Connection closed unexpectedly before we could close the rpc interface')
            return

        self._command_task.async_command(['_disable_rpcs', handle, services], self._on_interface_finished,
                                         {'connection_id': conn_id, 'callback': callback})

    def _on_interface_finished(self, result):
        success, retval, context = self._parse_return(result)
        callback = context['callback']

        if retval is not None and 'failure_reason' in retval:
            failure = retval['failure_reason']
        else:
            failure = None

        callback(context['connection_id'], self.id, success, failure)

    def _handle_event(self, event):
        # See https://www.silabs.com/documents/login/reference-manuals/Bluetooth_Smart_Software-BLE-1.7-API-RM.PDF
        # page 109 for reference on scan event packets
        if event.command_class == 6 and event.command == 0:
            self._process_scan_event(event)
        elif event.command_class == 3 and event.command == 4:
            # Handle disconnect event
            conn, reason = unpack("<BH", event.payload)

            conndata = self._get_connection(conn)

            if not conndata:
                self._logger.warning("Disconnection event for conn not in table %d", conn)
                return

            state = conndata['state']
            self._logger.warning('Disconnection event, handle=%d, reason=0x%X, state=%s', conn, reason,
                                 state)

            if state == 'preparing':
                conndata['failure_reason'] = 'Early disconnect, reason=%s' % reason
                conndata['error_code'] = reason
            elif state == 'started':
                pass
            elif state == 'connected':
                pass

            if 'disconnect_handler' in conndata:
                callback = conndata['disconnect_handler']
                callback(conndata['connection_id'], conn, True, 'Disconnected')

            self._remove_connection(conn)

            # If we were not told how to handle this disconnection, report that it happened
            if 'disconnect_handler' not in conndata:
                self._trigger_callback('on_disconnect', self.id, conndata['connection_id'])

        elif event.command_class == 4 and event.command == 5:
            # Handle notifications
            conn, = unpack("<B", event.payload[:1])
            at_handle, value = bgapi_structures.process_notification(event)

            conndata = self._get_connection(conn)

            if conndata is None:
                self._logger.warning("Recieved notification for an unknown connection, handle=%d" % at_handle)
                return

            parser = conndata['parser']

            try:
                char_uuid = bgapi_structures.handle_to_uuid(at_handle, conndata['services'])
            except ValueError:
                self._logger.warning("Notification from characteristic not in gatt table, ignoring it, handle=%d" % at_handle)
                return

            if char_uuid == TileBusStreamingCharacteristic:
                parser.add_data(value)
            elif char_uuid == TileBusTracingCharacteristic:
                self._trigger_callback('on_trace', conndata['connection_id'], bytearray(value))
            else:
                self._logger.warning("Notification from unknown characteristic (not streaming or tracing), ignoring it, handle=%d" % at_handle)
        else:
            self._logger.warning('Unhandled BLE event: ' + str(event))

    def _process_scan_event(self, response):
        """Parse the BLE advertisement packet.

        If it's an IOTile device, parse and add to the scanned devices. Then,
        parse advertisement and determine if it matches V1 or V2.  There are
        two supported type of advertisements:

        v1: There is both an advertisement and a scan response (if active scanning
            is enabled).
        v2: There is only an advertisement and no scan response.
        """

        payload = response.payload
        length = len(payload) - 10

        if length < 0:
            return

        rssi, packet_type, sender, _addr_type, _bond, data = unpack("<bB6sBB%ds" % length, payload)
        string_address = ':'.join([format(x, "02X") for x in bytearray(sender[::-1])])

        # Scan data is prepended with a length
        if len(data) > 0:
            data = bytearray(data[1:])
        else:
            data = bytearray([])

        # If this is an advertisement packet, see if its an IOTile device
        # packet_type = 4 is scan_response, 0, 2 and 6 are advertisements
        if packet_type in (0, 2, 6):
            if len(data) != 31:
                return

            if data[22] == 0xFF and data[23] == 0xC0 and data[24] == 0x3:
                self._parse_v1_advertisement(rssi, string_address, data)
            elif data[3] == 27 and data[4] == 0x16 and data[5] == 0xdd and data[6] == 0xfd:
                self._parse_v2_advertisement(rssi, string_address, data)
            else:
                pass # This just means the advertisement was from a non-IOTile device
        elif packet_type == 4:
            self._parse_v1_scan_response(string_address, data)

    def _parse_v2_advertisement(self, rssi, sender, data):
        """ Parse the IOTile Specific advertisement packet"""

        if len(data) != 31:
            return

        # We have already verified that the device is an IOTile device
        # by checking its service data uuid in _process_scan_event so
        # here we just parse out the required information

        device_id, reboot_low, reboot_high_packed, flags, timestamp, \
        battery, counter_packed, broadcast_stream_packed, broadcast_value, \
        _mac = unpack("<LHBBLBBHLL", data[7:])

        reboots = (reboot_high_packed & 0xF) << 16 | reboot_low
        counter = counter_packed & ((1 << 5) - 1)
        broadcast_multiplex = counter_packed >> 5
        broadcast_toggle = broadcast_stream_packed >> 15
        broadcast_stream = broadcast_stream_packed & ((1 << 15) - 1)

        # Flags for version 2 are:
        #   bit 0: Has pending data to stream
        #   bit 1: Low voltage indication
        #   bit 2: User connected
        #   bit 3: Broadcast data is encrypted
        #   bit 4: Encryption key is device key
        #   bit 5: Encryption key is user key
        #   bit 6: broadcast data is time synchronized to avoid leaking
        #   information about when it changes

        info = {'connection_string': sender,
                'uuid': device_id,
                'pending_data': bool(flags & (1 << 0)),
                'low_voltage': bool(flags & (1 << 1)),
                'user_connected': bool(flags & (1 << 2)),
                'signal_strength': rssi,
                'reboot_counter': reboots,
                'sequence': counter,
                'broadcast_toggle': broadcast_toggle,
                'timestamp': timestamp,
                'battery': battery / 32.0,
                'advertising_version':2}

        self._trigger_callback('on_scan', self.id, info, self.ExpirationTime)

        # If there is a valid reading on the advertising data, broadcast it
        if broadcast_stream != 0xFFFF & ((1 << 15) - 1):
            if self._throttle_broadcast and \
               self._check_update_seen_broadcast(sender, timestamp, broadcast_stream, broadcast_value,
                                                 broadcast_toggle, counter=counter, channel=broadcast_multiplex):
                return

            reading = IOTileReading(timestamp, broadcast_stream, broadcast_value, reading_time=datetime.datetime.utcnow())
            report = BroadcastReport.FromReadings(info['uuid'], [reading], timestamp)
            self._trigger_callback('on_report', None, report)

    def _check_update_seen_broadcast(self, sender, device_time, stream, value, toggle=None, counter=None, channel=0):
        key = (sender, channel)

        info = self._broadcast_state.get(key)

        if info is not None:
            old_time, old_stream, old_value, old_toggle, old_counter = info

            if toggle is not None and counter is not None:
                if old_toggle == toggle and old_counter == counter:
                    return True
            else:
                if old_value == value and old_stream == stream and old_time == device_time:
                    return True

        self._broadcast_state[key] = (device_time, stream, value, toggle, counter)
        return False


    def _parse_v1_advertisement(self, rssi, sender, advert):
        if len(advert) != 31:
            return

        # Make sure the scan data comes back with an incomplete UUID list
        if advert[3] != 17 or advert[4] != 6:
            return


        # Make sure the uuid is our tilebus UUID
        if advert[5:21] == TileBusService.bytes_le:
            # Now parse out the manufacturer specific data
            manu_data = advert[21:]

            _length, _datatype, _manu_id, device_uuid, flags = unpack("<BBHLH", manu_data)

            # Flags for version 1 are:
            #   bit 0: whether we have pending data
            #   bit 1: whether we are in a low voltage state
            #   bit 2: whether another user is connected
            #   bit 3: whether we support robust reports
            #   bit 4: whether we allow fast writes
            info = {'connection_string': sender,
                    'uuid': device_uuid,
                    'pending_data': bool(flags & (1 << 0)),
                    'low_voltage': bool(flags & (1 << 1)),
                    'user_connected': bool(flags & (1 << 2)),
                    'signal_strength': rssi,
                    'advertising_version': 1}

            if self._active_scan:
                self.partial_scan_responses[sender] = info
            else:
                self._trigger_callback('on_scan', self.id, info, self.ExpirationTime)

    def _parse_v1_scan_response(self, sender, scan_data):
        if len(scan_data) != 31:
            return

        info = self.partial_scan_responses.pop(sender, None)
        if info is None:
            return

        # Check if this is a scan response packet from an iotile based device
        _length, _datatype, _manu_id, voltage, stream, reading, reading_time, curr_time = unpack("<BBHHHLLL11x", scan_data)

        info['voltage'] = voltage / 256.0
        info['current_time'] = curr_time
        info['last_seen'] = datetime.datetime.now()

        self._trigger_callback('on_scan', self.id, info, self.ExpirationTime)

        # If there is a valid reading on the advertising data, broadcast it
        if stream != 0xFFFF:
            if self._throttle_broadcast and self._check_update_seen_broadcast(sender, reading_time, stream, reading):
                return

            reading = IOTileReading(reading_time, stream, reading, reading_time=datetime.datetime.utcnow())
            report = BroadcastReport.FromReadings(info['uuid'], [reading], curr_time)
            self._trigger_callback('on_report', None, report)

    def probe_services(self, handle, conn_id, callback):
        """Given a connected device, probe for its GATT services and characteristics

        Args:
            handle (int): a handle to the connection on the BLED112 dongle
            conn_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): Callback to be called when this procedure finishes
        """

        self._command_task.async_command(['_probe_services', handle], callback,
                                         {'connection_id': conn_id, 'handle': handle})

    def probe_characteristics(self, conn_id, handle, services):
        """Probe a device for all characteristics defined in its GATT table

        This routine must be called after probe_services and passed the services dictionary
        produced by that method.

        Args:
            handle (int): a handle to the connection on the BLED112 dongle
            conn_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            services (dict): A dictionary of GATT services produced by probe_services()
        """
        self._command_task.async_command(['_probe_characteristics', handle, services],
                                         self._probe_characteristics_finished, {'connection_id': conn_id,
                                                                                'handle': handle,
                                                                                'services': services})

    def initialize_system_sync(self):
        """Remove all active connections and query the maximum number of supported connections
        """

        retval = self._command_task.sync_command(['_query_systemstate'])

        self.maximum_connections = retval['max_connections']

        for conn in retval['active_connections']:
            self._connections[conn] = {'handle': conn, 'connection_id': len(self._connections)}
            self.disconnect_sync(0)

        # If the dongle was previously left in a dirty state while still scanning, it will
        # not allow new scans to be started.  So, forcibly stop any in progress scans.
        # This throws a hardware error if scanning is not in progress which should be ignored.
        try:
            self.stop_scan()
        except HardwareError:
            # If we errored our it is because we were not currently scanning, so make sure
            # we update our self.scanning flag (which would not be updated by stop_scan since
            # it raised an exception.)
            self.scanning = False

        self._command_task.sync_command(['_set_mode', 0, 0]) #Disable advertising

        self._logger.info("BLED112 adapter supports %d connections", self.maximum_connections)

    def _on_disconnect(self, result):
        """Callback called when disconnection command finishes

        Args:
            result (dict): result returned from diconnection command
        """

        success, _, context = self._parse_return(result)

        callback = context['callback']
        connection_id = context['connection_id']
        handle = context['handle']

        callback(connection_id, self.id, success, "No reason given")
        self._remove_connection(handle)  # NB Cleanup connection after callback in case it needs the connection info

    @classmethod
    def _parse_return(cls, result):
        """Extract the result, return value and context from a result object
        """

        return_value = None
        success = result['result']
        context = result['context']

        if 'return_value' in result:
            return_value = result['return_value']

        return success, return_value, context

    def _find_handle(self, conn_id):
        for handle, data in viewitems(self._connections):
            if data['connection_id'] == conn_id:
                return handle

        raise ValueError("connection id not found: %d" % conn_id)

    def _get_connection(self, handle, expect_state=None):
        """Get a connection object, logging an error if its in an unexpected state
        """

        conndata = self._connections.get(handle)

        if conndata and expect_state is not None and conndata['state'] != expect_state:
            self._logger.error("Connection in unexpected state, wanted=%s, got=%s", expect_state,
                               conndata['state'])
        return conndata

    def _remove_connection(self, handle):
        self._connections.pop(handle, None)

    def _on_connection_finished(self, result):
        """Callback when the connection attempt to a BLE device has finished

        This function if called when a new connection is successfully completed

        Args:
            event (BGAPIPacket): Connection event
        """

        success, retval, context = self._parse_return(result)
        conn_id = context['connection_id']
        callback = context['callback']

        if success is False:
            callback(conn_id, self.id, False, 'Timeout opening connection')

            with self.count_lock:
                self.connecting_count -= 1
            return

        handle = retval['handle']
        context['disconnect_handler'] = self._on_connection_failed
        context['connect_time'] = time.time()
        context['state'] = 'preparing'
        self._connections[handle] = context

        self.probe_services(handle, conn_id, self._probe_services_finished)

    def _on_connection_failed(self, conn_id, handle, clean, reason):
        """Callback called from another thread when a connection attempt has failed.
        """

        with self.count_lock:
            self.connecting_count -= 1

        self._logger.info("_on_connection_failed conn_id=%d, reason=%s", conn_id, str(reason))

        conndata = self._get_connection(handle)

        if conndata is None:
            self._logger.info("Unable to obtain connection data on unknown connection %d", conn_id)
            return

        callback = conndata['callback']
        conn_id = conndata['connection_id']
        failure_reason = conndata['failure_reason']

        # If this was an early disconnect from the device, automatically retry
        if 'error_code' in conndata and conndata['error_code'] == 0x23e and conndata['retries'] > 0:
            self._remove_connection(handle)
            self.connect_async(conn_id, conndata['connection_string'], callback, conndata['retries'] - 1)
        else:
            callback(conn_id, self.id, False, failure_reason)
            self._remove_connection(handle)

    def _probe_services_finished(self, result):
        """Callback called after a BLE device has had its GATT table completely probed

        Args:
            result (dict): Parameters determined by the probe and context passed to the call to
                probe_device()
        """

        #If we were disconnected before this function is called, don't proceed
        handle = result['context']['handle']
        conn_id = result['context']['connection_id']

        conndata = self._get_connection(handle, 'preparing')

        if conndata is None:
            self._logger.info('Connection disconnected before prob_services_finished, conn_id=%d',
                              conn_id)
            return

        if result['result'] is False:
            conndata['failed'] = True
            conndata['failure_reason'] = 'Could not probe GATT services'
            self.disconnect_async(conn_id, self._on_connection_failed)
        else:
            conndata['services_done_time'] = time.time()
            self.probe_characteristics(result['context']['connection_id'], result['context']['handle'], result['return_value']['services'])

    def _probe_characteristics_finished(self, result):
        """Callback when BLE adapter has finished probing services and characteristics for a device

        Args:
            result (dict): Result from the probe_characteristics command
        """

        handle = result['context']['handle']
        conn_id = result['context']['connection_id']

        conndata = self._get_connection(handle, 'preparing')

        if conndata is None:
            self._logger.info('Connection disconnected before probe_char... finished, conn_id=%d',
                              conn_id)
            return

        callback = conndata['callback']

        if result['result'] is False:
            conndata['failed'] = True
            conndata['failure_reason'] = 'Could not probe GATT characteristics'
            self.disconnect_async(conn_id, self._on_connection_failed)
            return

        # Validate that this is a proper IOTile device
        services = result['return_value']['services']
        if TileBusService not in services:
            conndata['failed'] = True
            conndata['failure_reason'] = 'TileBus service not present in GATT services'
            self.disconnect_async(conn_id, self._on_connection_failed)
            return

        conndata['chars_done_time'] = time.time()
        service_time = conndata['services_done_time'] - conndata['connect_time']
        char_time = conndata['chars_done_time'] - conndata['services_done_time']
        total_time = service_time + char_time
        conndata['state'] = 'connected'
        conndata['services'] = services

        # Create a report parser for this connection for when reports are streamed to us
        conndata['parser'] = IOTileReportParser(report_callback=self._on_report, error_callback=self._on_report_error)
        conndata['parser'].context = conn_id

        del conndata['disconnect_handler']

        with self.count_lock:
            self.connecting_count -= 1

        self._logger.info("Total time to connect to device: %.3f (%.3f enumerating services, %.3f enumerating chars)", total_time, service_time, char_time)
        callback(conndata['connection_id'], self.id, True, None)

    def _on_report(self, report, connection_id):
        # self._logger.info('Received report: %s', str(report))
        self._trigger_callback('on_report', connection_id, report)

        return False

    def _on_report_error(self, code, message, connection_id):
        print("Report Error, code=%d, message=%s" % (code, message))
        self._logger.critical("Error receiving reports, no more reports will be processed on this adapter, code=%d, msg=%s", code, message)

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter, should be called every second
        """

        if self.stopped:
            return

        # Check if we should start scanning again
        if not self.scanning and len(self._connections) == 0 and self.connecting_count == 0:
            self._logger.info("Restarting scan for devices")
            self.start_scan(self._active_scan)
            self._logger.info("Finished restarting scan for devices")
