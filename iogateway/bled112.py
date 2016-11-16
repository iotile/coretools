# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from collections import namedtuple
from Queue import Queue, Empty
import time
import struct
import threading
import logging
import datetime
import uuid
import copy
import serial
from iotilecore.utilities.packed import unpack
from async_packet import AsyncPacketBuffer

import device
from bgapi_structures import process_gatt_service, process_attribute, process_read_handle
from bgapi_structures import parse_characteristic_declaration

def packet_length(header):
    """
    Find the BGAPI packet length given its header
    """

    highbits = header[0] & 0b11
    lowbits = header[1]

    return (highbits << 8) | lowbits

BGAPIPacket = namedtuple("BGAPIPacket", ["is_event", "command_class", "command", "payload"])

class BLED112CommandProcessor(threading.Thread):
    def __init__(self, stream, commands):
        super(BLED112CommandProcessor, self).__init__()

        self._stream = stream
        self._commands = commands
        self._stop = threading.Event()
        self._logger = logging.getLogger('server.ble.raw')
        self.event_handler = None

    def run(self):
        while not self._stop.is_set():
            try:
                self._process_events()
                cmdargs, callback, sync, context = self._commands.get(timeout=0.01)
                cmd = cmdargs[0]

                if len(cmdargs) > 0:
                    args = cmdargs[1:]
                else:
                    args = []

                self._logger.info('Started command: ' + cmd)
                if hasattr(self, cmd):
                    result, retval = getattr(self, cmd)(*args)
                else:
                    pass #FIXME: Log an error for an invalid command
                self._logger.info('Finished command: ' + cmd)

                result_obj = {}
                result_obj['command'] = cmd
                result_obj['result'] = bool(result)
                result_obj['return_value'] = retval
                result_obj['context'] = context

                if callback:
                    callback(result_obj)
            except Empty:
                pass

    def _set_scan_parameters(self, interval=2100, window=2100, active=False):
        """
        Set the scan interval and window in units of ms and set whether active scanning is performed
        """

        active_num = 0
        if bool(active):
            active_num = 1

        interval_num = int(interval*1000/625)
        window_num = int(window*1000/625)

        payload = struct.pack("<HHB", interval_num, window_num, active_num)

        response = self._send_command(6, 7, payload)
        if response.payload[0] != 0:
            raise ValueError("Could not set scanning parameters", error_code=response.payload[0], response=response)

    def _query_systemstate(self):
        """Query the maximum number of connections supported by this adapter
        """

        def status_filter_func(event):
            if event.command_class == 3 and event.command == 0:
                return True

            return False

        response = self._send_command(0, 6, [])
        maxconn, = unpack("<B", response.payload)

        events = self._wait_process_events(0.5, status_filter_func, lambda x: False)

        conns = []
        for event in events:
            handle, flags, addr, addr_type, interval, timeout, lat, bond = unpack("<BB6sBHHHB", event.payload)
            
            if flags != 0:
                conns.append(handle)

        return True, {'max_connections': maxconn, 'active_connections': conns}
        
    def _start_scan(self, active):
        """Begin scanning forever
        """

        self._set_scan_parameters(active=active)

        try:
            response = self._send_command(6, 2, [2])
            if response.payload[0] != 0:
                raise ValueError("Could not initiate scan for ble devices, error_code=%d, response=%s" % (response.payload[0], response))
        except ValueError as err:
            self._logger.error('Error scanning for devices: ' + str(err))
            return False, None

        return True, None

    def _stop_scan(self):
        """Stop scanning for BLE devices
        """

        try:
            response = self._send_command(6, 4, [])
            if response.payload[0] != 0:
                raise ValueError("Could not stop scan for ble devices")
        except ValueError as err:
            self._logger.error('Error scanning for devices: ' + str(err))
            return False, None

        return True, None

    def _probe_services(self, handle):
        """Probe for all primary services and characteristics in those services

        Args:
            handle (int): the connection handle to probe
        """

        code = 0x2800

        def event_filter_func(event):
            if (event.command_class == 4 and event.command == 2):
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == handle
            
            return False

        def end_filter_func(event):
            if (event.command_class == 4 and event.command == 1):
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == handle
            
            return False

        payload = struct.pack('<BHHBH', handle, 1, 0xFFFF, 2, code)
        response = self._send_command(4, 1, payload)

        handle, result = unpack("<BH", response.payload)
        if result != 0:
            return False, None

        events = self._wait_process_events(0.5, event_filter_func, end_filter_func)
        gatt_events = filter(event_filter_func, events)
        end_events = filter(end_filter_func, events)

        if len(end_events) == 0:
            return False, None

        #Make sure we successfully probed the gatt table
        end_event = end_events[0]
        _, result, _ = unpack("<BHH", end_event.payload)
        if result != 0:
            self._logger.warn("Error enumerating GATT table, protocol error code = %d (0x%X)" % (result, result))
            return False, None

        services = {}
        for event in gatt_events:
            process_gatt_service(services, event)

        return True, {'services': services}

    def _probe_characteristics(self, conn, services, timeout=5.0):
        """Probe gatt services for all associated characteristics in a BLE device

        Args:
            conn (int): the connection handle to probe
            services (dict): a dictionary of services produced by probe_services()
            timeout (float): the maximum number of seconds to spend in any single task
        """

        for service in services.itervalues():
            success, result = self._enumerate_handles(conn, service['start_handle'], 
                                                      service['end_handle'])

            if not success:
                return False, None

            attributes = result['attributes']

            service['characteristics'] = {}

            last_char = None
            for handle, attribute in attributes.iteritems():
                if attribute['uuid'].hex[-4:] == '0328':
                    success, result = self._read_handle(conn, handle, timeout)
                    if not success:
                        return False, None

                    value = result['data']
                    char = parse_characteristic_declaration(value)
                    service['characteristics'][char['uuid']] = char
                    last_char = char
                elif attribute['uuid'].hex[-4:] == '0229':
                    if last_char is None:
                        return False, None

                    success, result = self._read_handle(conn, handle, timeout)
                    if not success:
                        return False, None

                    value = result['data']
                    assert len(value) == 2
                    value, = unpack("<H", value)

                    last_char['client_configuration'] = {'handle': handle, 'value': value}

        return True, {'services': services}

    def _enumerate_handles(self, conn, start_handle, end_handle, timeout=5.0):
        conn_handle = conn

        def event_filter_func(event):
            if event.command_class == 4 and event.command == 4:
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == conn_handle
            
            return False

        def end_filter_func(event):
            if event.command_class == 4 and event.command == 1:
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == conn_handle
            
            return False

        payload = struct.pack("<BHH", conn_handle, start_handle, end_handle)
        response = self._send_command(4, 3, payload)

        handle, result = unpack("<BH", response.payload)

        if result != 0:
            return False, None

        events = self._wait_process_events(timeout, event_filter_func, end_filter_func)
        handle_events = filter(event_filter_func, events)

        attrs = {}
        for event in handle_events:
            process_attribute(attrs, event)

        return True, {'attributes': attrs}

    def _read_handle(self, conn, handle, timeout=5.0):
        conn_handle = conn
        payload = struct.pack("<BH", conn_handle, handle)
        response = self._send_command(4, 4, payload)

        ignored_handle, result = unpack("<BH", response.payload)

        if result != 0:
            self._logger.warn("Error reading handle %d, result=%d" % (handle, result))
            return False, None

        def handle_value_func(event):
            if (event.command_class == 4 and event.command == 5):
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == conn_handle

        def handle_error_func(event):
            if (event.command_class == 4 and event.command == 1):
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == conn_handle 

        events = self._wait_process_events(5.0, lambda x: False, lambda x: handle_value_func(x) or handle_error_func(x))
        if len(events) != 1:
            return False, None

        if handle_error_func(events[0]):
            return False, None

        handle_event = events[0]
        handle_type, handle_data = process_read_handle(handle_event)

        return True, {'type': handle_type, 'data': handle_data}

    def _connect(self, address):
        """Connect to a device given its uuid
        """

        latency = 0
        conn_interval_min = 6
        conn_interval_max = 100
        timeout = 1.0

        #Allow passing either a binary address or a hex string
        if isinstance(address, basestring) and len(address) > 6:
            address = address.replace(':', '')
            address = str(bytearray.fromhex(address)[::-1])

        #Allow simple determination of whether a device has a public or private address
        #This is not foolproof
        private_bits = ord(address[-1]) >> 6
        if private_bits == 0b11:
            address_type = 1
        else:
            address_type = 0

        payload = struct.pack("<6sBHHHH", address, address_type, conn_interval_min,
                              conn_interval_max, int(timeout*100.0), latency)
        response = self._send_command(6, 3, payload)

        result, handle = unpack("<HB", response.payload)
        if result != 0:
            return False, None

        #Now wait for the connection event that says we connected or kill the attempt after timeout
        def conn_succeeded(event):
            if event.command_class == 3 and event.command == 0:
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == handle

        #FIXME Hardcoded timeout
        events = self._wait_process_events(4.0, lambda x: False, conn_succeeded)
        if len(events) != 1:
            self._stop_scan()
            return False, None

        handle, _, addr, _, interval, timeout, latency, _ = unpack("<BB6sBHHHB", events[0].payload)
        formatted_addr = ":".join(["%02X" % ord(x) for x in addr])
        self._logger.info('Connected to device %s with interval=%d, timeout=%d, latency=%d',
                          formatted_addr, interval, timeout, latency)

        connection = {"handle": handle}
        return True, connection

    def _disconnect(self, handle):
        """Disconnect from a device that we have previously connected to
        """

        payload = struct.pack('<B', handle)
        response = self._send_command(3, 0, payload)

        conn_handle, result = unpack("<BH", response.payload)
        if result != 0:
            self._logger.info("Disconnection failed result=%d", result)
            return False, None

        assert conn_handle == handle

        def disconnect_succeeded(event):
            if event.command_class == 3 and event.command == 4:
                event_handle, = unpack("B", event.payload[0:1])
                return event_handle == handle

            return False

        #FIXME Hardcoded timeout
        events = self._wait_process_events(3.0, lambda x: False, disconnect_succeeded)
        if len(events) != 1:
            return False, None

        return True, {'handle': handle}

    def _send_command(self, cmd_class, command, payload, timeout=3.0):
        """
        Send a BGAPI packet to the dongle and return the response
        """

        if len(payload) > 60:
            return ValueError("Attempting to send a BGAPI packet with length > 60 is not allowed", actual_length=len(payload), command=command, command_class=cmd_class)

        header = bytearray(4)
        header[0] = 0
        header[1] = len(payload)
        header[2] = cmd_class
        header[3] = command

        packet = header + bytearray(payload)
        self._logger.info('Sending: ' + ':'.join([format(x, "02X") for x in packet]))
        self._stream.write(packet)

        #Every command has a response so wait for the response here
        response = self._receive_packet(timeout)
        return response

    def _receive_packet(self, timeout=3.0):
        """
        Receive a response packet to a command
        """

        while True:
            response_data = self._stream.read_packet(timeout=timeout)
            response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

            if response.is_event:
                if self.event_handler is not None:
                    self.event_handler(response)
                
                continue

            return response

    def stop(self):
        self._stop.set()
        self.join()

    def sync_command(self, cmd):
        done_event = threading.Event()
        results = []
        def done_callback(result):
            results.append(result)
            done_event.set()

        self._commands.put((cmd, done_callback, True, None))

        done_event.wait()

        if len(results) == 0:
            return None

        return results[0]

    def async_command(self, cmd, callback, context):
        self._commands.put((cmd, callback, False, context))

    def _process_events(self, return_filter=None):
        to_return = []

        try:
            while True:
                event_data = self._stream.queue.get_nowait()
                event = BGAPIPacket(is_event=(event_data[0] == 0x80), command_class=event_data[2],
                                    command=event_data[3], payload=event_data[4:])

                if not event.is_event:
                    self._logger.error('Received response when we should have only received events:' + str(event))
                elif return_filter is not None and return_filter(event):
                    to_return.append(event)
                elif self.event_handler is not None:
                    self.event_handler(event)
        except Empty:
            pass

        return to_return

    def _wait_process_events(self, total_time, return_filter, end_filter):
        """Synchronously process events until a specific event is found or we timeout

        Args:
            total_time (float): The aproximate maximum number of seconds we should wait for the end event
            return_filter (callable): A function that returns True for events we should return and not process
                normally via callbacks to the IOLoop
            end_filter (callable): A function that returns True for the end event that we are looking for to
                stop processing.

        Returns:
            list: A list of events that matched return_filter or end_filter
        """
        acc = []

        delta = 0.01
        curr_time = 0.0
        
        while curr_time < total_time:
            events = self._process_events(lambda x: return_filter(x) or end_filter(x))
            acc += events

            for event in events:
                if end_filter(event):
                    return acc

            time.sleep(delta)

            curr_time += delta

        return acc


class BLED112Manager(device.DeviceAdapter):
    """Callback based BLED112 wrapper supporting multiple simultaneous connections 
    """

    ExpirationTime = 60 #Expire devices 60 seconds after seeing them

    TileBusService = uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')
    TileBusSendHeaderCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000320')
    TileBusSendPayloadCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000420')
    TileBusReceiveHeaderCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000120')
    TileBusReceivePayloadCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000220')
    TileBusStreamingCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000520')
    TileBusHighSpeedCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000620')

    def __init__(self, port):
        super (BLED112Manager, self).__init__()

        self._serial_port = serial.Serial(port, 256000, timeout=0.01, rtscts=True)
        self._stream = AsyncPacketBuffer(self._serial_port, header_length=4, length_function=packet_length)
        self._commands = Queue()
        self._command_task = BLED112CommandProcessor(self._stream, self._commands)
        self._command_task.event_handler = self._handle_event
        self._command_task.start()

        #Prepare internal state of scannable and in progress devices
        self.partial_scan_responses = {}
        self._connections = {}
        self.count_lock = threading.Lock()
        self.connecting_count = 0
        self.maximum_connections = 0

        self._logger = logging.getLogger('ble.manager')
        self._command_task._logger.setLevel(logging.WARNING)

        self.initialize_system_sync()
        self.start_scan()

    def can_connect(self):
        """Check if this adapter can take another connection

        Returns:
            bool: whether there is room for one more connection
        """

        return len(self._connections) < self.maximum_connections

    def _handle_event(self, event):
        if event.command_class == 6 and event.command == 0:
            #Handle scan response events
            self._parse_scan_response(event)
        elif event.command_class == 3 and event.command == 4:
            #Handle disconnect event
            conn, reason = unpack("<BH", event.payload)
            if conn not in self._connections:
                self._logger.warn("Disconnection event for conn not in table %d", conn)
                return

            conndata = self._get_connection(conn)
            state = conndata['state']
            self._logger.warn('Disconnection event, handle=%d, reason=0x%X, state=%s', conn, reason,
                              state)

            if state == 'preparing':
                conndata['failure_reason'] = 'Early disconnect, reason=%s' % reason
            elif state == 'started':
                pass
            elif state == 'connected':
                pass

            if 'disconnect_handler' in conndata:
                callback = conndata['disconnect_handler']
                callback(conndata['connection_id'], conn, True, 'Disconnected')

            if conn in self._connections:
                del self._connections[conn]
        else:
            self._logger.warn('Unhandled BLE event: ' + str(event))

    def _parse_scan_response(self, response):
        """Parse the IOTile specific data structures in the BLE advertisement packets and add the device to our list of scanned devices
        """

        payload = response.payload
        length = len(payload) - 10

        if length < 0:
            return #FIXME: Log an error here

        rssi, packet_type, sender, addr_type, bond, data = unpack("<bB6sBB%ds" % length, payload)

        parsed ={}
        parsed['rssi'] = rssi
        parsed['type'] = packet_type
        parsed['address_raw'] = sender
        parsed['address'] = ':'.join([format(ord(x), "02X") for x in sender[::-1]])
        parsed['address_type'] = addr_type 
        
        #Scan data is prepended with a length
        if len(data)  > 0:
            parsed['scan_data'] = bytearray(data[1:])
        else:
            parsed['scan_data'] = bytearray([])

        #If this is an advertisement response, see if its an IOTile device
        if parsed['type'] == 0 or parsed['type'] == 6:
            scan_data = parsed['scan_data']

            if len(scan_data) < 29:
                return #FIXME: Log an error here

            #Skip BLE flags
            scan_data = scan_data[3:]

            #Make sure the scan data comes back with an incomplete UUID list
            if scan_data[0] != 17 or scan_data[1] != 6:
                return #FIXME: Log an error here

            uuid_buf = scan_data[2:18]
            assert len(uuid_buf) == 16
            service = uuid.UUID(bytes_le=str(uuid_buf))

            if service == self.TileBusService:
                #Now parse out the manufacturer specific data
                manu_data = scan_data[18:]
                assert len(manu_data) == 10

                #FIXME: Move flag parsing code flag definitions somewhere else
                length, datatype, manu_id, device_uuid, flags = unpack("<BBHLH", manu_data)
                
                pending = False
                low_voltage = False
                user_connected = False
                if flags & (1 << 0):
                    pending = True
                if flags & (1 << 1):
                    low_voltage = True
                if flags & (1 << 2):
                    user_connected = True

                self.partial_scan_responses[parsed['address']] = {  'user_connected': user_connected, 'connection_string': parsed['address'], 
                                                                    'uuid': device_uuid, 'pending_data': pending, 'low_voltage': low_voltage, 
                                                                    'signal_strength': parsed['rssi']}
        elif parsed['type'] == 4 and parsed['address'] in self.partial_scan_responses:
            #Check if this is a scan response packet from an iotile based device
            scan_data = parsed['scan_data']
            if len(scan_data) != 31:
                return #FIXME: Log an error here

            length, datatype, manu_id, voltage, stream, reading, reading_time, curr_time = unpack("<BBHHHLLL11x", scan_data)
            
            info = self.partial_scan_responses[parsed['address']]
            info['voltage'] = voltage / 256.0
            info['current_time'] = curr_time
            info['last_seen'] = datetime.datetime.now()

            if stream != 0xFFFF:
                info['visible_readings'] = [(stream, reading_time, reading),]

            del self.partial_scan_responses[parsed['address']]
            self.manager.device_found_callback(self.id, info, self.ExpirationTime)

    def stop(self):
        """Safely stop this BLED112 instance without leaving it in a weird state

        """

        if self.scanning:
            self.stop_scan()

        #Make a copy since this will change size as we disconnect
        con_copy = copy.copy(self._connections)

        for _, context in con_copy.iteritems():
            self.disconnect_sync(context['connection_id'])

        self._command_task.stop()
        self._stream.stop()

    def stop_scan(self):
        self._command_task.sync_command(['_stop_scan'])
        self.scanning = False

    def start_scan(self, active=True):
        self._command_task.sync_command(['_start_scan', active])
        self.scanning = True

    def connect(self, connection_string, conn_id, callback):
        """Connect to a device by its connection_string

        This function asynchronously connects to a device by its BLE address passed in the
        connection_string parameter and calls callback when finished.  Callback is called
        on either success or failure with the signature:

        callback(conn_id: int, result: bool, value: None)

        Args:
            connection_string (string): A BLE address is XX:YY:ZZ:AA:BB:CC format
            conn_id (int): A unique integer set by the caller for referring to this connection
                once created
            callback (callable): A callback function called when the connection has succeeded or
                failed
        """

        context = {}
        context['connection_id'] = conn_id
        context['callback'] = callback

        #Don't scan while we attempt to connect to this device
        if self.scanning:
            self.stop_scan()

        with self.count_lock:
            self.connecting_count += 1
        
        self._command_task.async_command(['_connect', connection_string],
                                         self._on_connection_finished, context)

    def probe_services(self, handle, conn_id, callback):
        """Given a connected device, probe for its GATT services and characteristics

        Args:
            handle (int): a handle to the connection on the BLED112 dongle
            conn_id (int): a unique identifier for this connection on the DeviceManager 
                that owns this adapter.
            callback (callable): Callback to be called when this procedure finishes
        """

        self._command_task.async_command(['_probe_services', handle], callback, {'connection_id': conn_id, 'handle': handle})

    def probe_characteristics(self, conn_id, handle, services):
        """Probe a device for all characteristics defined in its GATT table

        This routine muts be called after probe_services and passed the services dictionary
        produced by that method.

        Args:
            handle (int): a handle to the connection on the BLED112 dongle
            conn_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            services (dict): A dictionary of GATT services produced by probe_services()
        """
        self._command_task.async_command(['_probe_characteristics', handle, services],
            self._probe_characteristics_finished, {'connection_id': conn_id, 'handle': handle, 
            'services': services})

    def initialize_system_sync(self):
        """Remove all active connections and query the maximum number of supported connections
        """

        result = self._command_task.sync_command(['_query_systemstate'])
        _, retval, _ = self._parse_return(result)

        self.maximum_connections = retval['max_connections']

        for conn in retval['active_connections']:
            self._connections[conn] = {'handle': conn, 'connection_id': len(self._connections)}
            self.disconnect_sync(0)

        self._logger.critical("BLED112 adapter supports %d connections", self.maximum_connections)

    def disconnect(self, conn_id, callback):
        """Disconnect from a device that has previously been connected

        Args:
            conn_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): A function called as callback(conn_id, handle, success, reason)
            when the disconnection finishes.  Disconnection can only either succeed or timeout.
        """

        found_handle = None
        #Find the handle by connection id
        for handle, conn in self._connections.iteritems():
            if conn['connection_id'] == conn_id:
                found_handle = handle

        if found_handle is None:
            callback(conn_id, 0, False, 'Invalid connection_id')
            return

        self._command_task.async_command(['_disconnect', found_handle], self._on_disconnect,
                                         {'connection_id': conn_id, 'handle': found_handle,
                                          'callback': callback})

    def disconnect_sync(self, conn_id):
        """Synchronously disconnect from a connected device

        """
        done = threading.Event()

        def disconnect_done(conn_id, handle, status, reason):
            done.set()

        self.disconnect(conn_id, disconnect_done)
        done.wait()

    def _on_disconnect(self, result):
        """Callback called when disconnection command finishes

        Args:
            result (dict): result returned from diconnection command
        """
        
        success, _, context = self._parse_return(result)

        callback = context['callback']
        connection_id = context['connection_id']
        handle = context['handle']

        del self._connections[handle]

        callback(connection_id, handle, success, "No reason given")

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

    def _get_connection(self, handle, expect_state=None):
        """Get a connection object, logging an error if its in an unexpected state
        """

        conndata = self._connections[handle]

        if expect_state is not None and conndata['state'] != expect_state:
            self._logger.error("Connection in unexpected state, wanted=%s, got=%s", expect_state,   
                               conndata['state'])
        return conndata

    def _on_connection_finished(self, result):
        """Callback when the connection attempt to a BLE device has finished

        This function if called by the event_handler when a new connection event is seen

        Args:
            event (BGAPIPacket): Connection event
        """

        success, retval, context = self._parse_return(result)
        conn_id = context['connection_id']
        callback = context['callback']

        if success is False:
            callback(conn_id, False, 'Timeout openning connection id %d' % conn_id)
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
        callback = conndata['callback']
        conn_id = conndata['connection_id']
        failure_reason = conndata['failure_reason']
        callback(conn_id, False, failure_reason)

        del self._connections[handle]

    def _probe_services_finished(self, result):
        """Callback called after a BLE device has had its GATT table completely probed

        Args:
            result (dict): Parameters determined by the probe and context passed to the call to
                probe_device()
        """

        #If we were disconnected before this function is called, don't proceed
        handle = result['context']['handle']
        conn_id = result['context']['connection_id']

        if handle not in self._connections:
            self._logger.info('Connection disconnected before prob_services_finished, conn_id=%d',
                              conn_id)
            return


        conndata = self._get_connection(handle, 'preparing')

        if result['result'] is False:
            conndata['failed'] = True
            conndata['failure_reason'] = 'Could not probe GATT services'
            self.disconnect(conn_id, self._on_connection_failed)
        else:
            conndata['services_done_time'] = time.time()
            self.probe_characteristics(result['context']['connection_id'], result['context']['handle'], result['return_value']['services'])

    def _on_disconnect_started(self, result):
        """Callback called when an attempt to disconnect from a device has been initiated
        """

        handle = result['context']['handle']
        callback = result['context']['callback']
        conn_id = result['context']['connection_id']
        conndata = self._get_connection(handle)

        if result['result'] is False:
            self._logger.error('Could not disconnect cleanly from device handle=%d', handle)
            callback(conn_id, handle, False, 'Could not initiate disconnection proces from device')
            conndata['state'] = 'zombie'
            return

        #We have started the disconnection process
        conndata['disconnecting'] = True

    def _probe_characteristics_finished(self, result):
        """Callback when BLE adapter has finished probing services and characteristics for a device 

        Args:
            result (dict): Result from the probe_characteristics command
        """

        handle = result['context']['handle']

        handle = result['context']['handle']
        conn_id = result['context']['connection_id']

        if handle not in self._connections:
            self._logger.info('Connection disconnected before probe_char... finished, conn_id=%d',
                              conn_id)
            return

        conndata = self._get_connection(handle, 'preparing')
        callback = conndata['callback']

        if result['result'] is False:
            conndata['failed'] = True
            conndata['failure_reason'] = 'Could not probe GATT characteristics'
            self.disconnect(conn_id, self._on_connection_failed)
            return

        #Validate that this is a proper IOTile device
        services = result['return_value']['services']
        if self.TileBusService not in services:
            conndata['failed'] = True
            conndata['failure_reason'] = 'TileBus service not present in GATT services'
            self.disconnect(conn_id, self._on_connection_failed)
            return

        conndata['chars_done_time'] = time.time()
        service_time = conndata['services_done_time'] - conndata['connect_time']
        char_time = conndata['chars_done_time'] - conndata['services_done_time']
        total_time = service_time + char_time
        conndata['state'] = 'connected'
        del conndata['disconnect_handler']

        with self.count_lock:
            self.connecting_count -= 1

        self._logger.info("Total time to connect to device: %.3f (%.3f enumerating services, %.3f enumerating chars)", total_time, service_time, char_time)
        callback(conndata['connection_id'], True, None)

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter, should be called every second
        """

        #Check if we should start scanning again
        if not self.scanning and len(self._connections) == 0 and self.connecting_count == 0:
            self._logger.info("Restarting scan for devices")
            self.start_scan()
            self._logger.info("Finished restarting scan for devices")
