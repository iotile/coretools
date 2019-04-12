from collections import namedtuple
import time
import struct
import threading
import logging
import functools
from queue import Empty
from iotile.core.utilities.packed import unpack
from iotile.core.utilities.async_tools import OperationManager, SharedLoop
from iotile.core.exceptions import HardwareError
from .tilebus import *
from .bgapi_structures import process_gatt_service, process_attribute, process_read_handle, process_notification
from .bgapi_structures import parse_characteristic_declaration
from .async_packet import InternalTimeoutError, DeviceNotConfiguredError

BGAPIPacket = namedtuple("BGAPIPacket", ["is_event", "command_class", "command", "payload"])


class AsyncBLED112CommandProcessor(threading.Thread):
    def __init__(self, stream, commands, stop_check_interval=0.01, loop=SharedLoop):
        super(AsyncBLED112CommandProcessor, self).__init__()

        self._stream = stream
        self._commands = commands
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())
        self._current_context = None
        self._current_callback = None
        self._event_check_interval = stop_check_interval

        self._loop = loop
        self._asyncio_cmd_lock = loop.create_lock()
        self.operations = OperationManager(loop=loop)

    def run(self):
        while True:
            try:
                self._process_events()
                event = self._commands.get(timeout=self._event_check_interval)
                if event is None:
                    self._logger.info("Shutting down bled112 thread due to stop command")
                    return

                cmdargs, callback, _, context = event
                cmd = cmdargs[0]

                if len(cmdargs) > 0:
                    args = cmdargs[1:]
                else:
                    args = []

                self._current_context = context
                self._current_callback = callback

                if hasattr(self, cmd):
                    res = getattr(self, cmd)(*args)
                else:
                    pass #FIXME: Log an error for an invalid command

                inprogress = False

                if len(res) == 2:
                    result, retval = res
                else:
                    result, retval, inprogress = res

                self._current_context = None
                self._current_callback = None

                result_obj = {}
                result_obj['command'] = cmd
                result_obj['result'] = bool(result)
                result_obj['return_value'] = retval
                result_obj['context'] = context

                if callback and inprogress is not True:
                    callback(result_obj)
            except Empty:
                pass
            except:
                self._logger.exception("Error executing command: %s", cmd)
                raise

    def _set_scan_parameters(self, interval=2100, window=2100, active=False):
        """Set the scan parameters like interval and window in units of ms."""

        active_num = 0
        if bool(active):
            active_num = 1

        interval_num = int(interval*1000/625)
        window_num = int(window*1000/625)

        payload = struct.pack("<HHB", interval_num, window_num, active_num)

        try:
            response = self._send_command(6, 7, payload)
            if response.payload[0] != 0:
                return False, {'reason': "Could not set scanning parameters", 'error': response.payload[0]}
        except InternalTimeoutError:
            return False, {'reason': 'Timeout waiting for response'}

        return True, None

    def _query_systemstate(self):
        """Query the maximum number of connections supported by this adapter."""

        def status_filter_func(event):
            if event.command_class == 3 and event.command == 0:
                return True

            return False

        try:
            response = self._send_command(0, 6, [])
            maxconn, = unpack("<B", response.payload)
        except InternalTimeoutError:
            return False, {'reason': 'Timeout waiting for command response'}

        events = self._wait_process_events(0.5, status_filter_func, lambda x: False)

        conns = []
        for event in events:
            handle, flags, addr, addr_type, interval, timeout, lat, bond = unpack("<BB6sBHHHB", event.payload)

            if flags != 0:
                conns.append(handle)

        return True, {'max_connections': maxconn, 'active_connections': conns}

    def _start_scan(self, active):
        """Begin scanning forever."""

        success, retval = self._set_scan_parameters(active=active)
        if not success:
            return success, retval

        try:
            response = self._send_command(6, 2, [2])
            if response.payload[0] != 0:
                self._logger.error('Error starting scan for devices, error=%d', response.payload[0])
                return False, {'reason': "Could not initiate scan for ble devices, error_code=%d, response=%s" % (response.payload[0], response)}
        except InternalTimeoutError:
            return False, {'reason': "Timeout waiting for response"}

        return True, None

    def _stop_scan(self):
        """Stop scanning for BLE devices."""

        try:
            response = self._send_command(6, 4, [])
            if response.payload[0] != 0:
                # Error code 129 means we just were not currently scanning
                if response.payload[0] != 129:
                    self._logger.error('Error stopping scan for devices, error=%d', response.payload[0])

                return False, {'reason': "Could not stop scan for ble devices"}
        except InternalTimeoutError:
            return False, {'reason': "Timeout waiting for response"}
        except DeviceNotConfiguredError:
            return True, {'reason': "Device not connected (did you disconnect the dongle?"}

        return True, None

    def _probe_services(self, handle):
        """Probe for all primary services and characteristics in those services.

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

        try:
            response = self._send_command(4, 1, payload)
        except InternalTimeoutError:
            return False, {'reason': 'Timeout waiting for command response'}

        handle, result = unpack("<BH", response.payload)
        if result != 0:
            return False, None

        events = self._wait_process_events(0.5, event_filter_func, end_filter_func)
        gatt_events = [x for x in events if event_filter_func(x)]
        end_events = [x for x in events if end_filter_func(x)]

        if len(end_events) == 0:
            return False, None

        #Make sure we successfully probed the gatt table
        end_event = end_events[0]
        _, result, _ = unpack("<BHH", end_event.payload)
        if result != 0:
            self._logger.warning("Error enumerating GATT table, protocol error code = %d (0x%X)" % (result, result))
            return False, None

        services = {}
        for event in gatt_events:
            process_gatt_service(services, event)

        return True, {'services': services}

    def _probe_characteristics(self, conn, services, timeout=5.0):
        """Probe gatt services for all associated characteristics in a BLE device.

        Args:
            conn (int): the connection handle to probe
            services (dict): a dictionary of services produced by probe_services()
            timeout (float): the maximum number of seconds to spend in any single task
        """

        for service in services.values():
            success, result = self._enumerate_handles(conn, service['start_handle'],
                                                      service['end_handle'])

            if not success:
                return False, None

            attributes = result['attributes']

            service['characteristics'] = {}

            last_char = None
            for handle, attribute in attributes.items():
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

    def _enable_rpcs(self, conn, services, timeout=1.0):
        """Prepare this device to receive RPCs."""

        #FIXME: Check for characteristic existence in a try/catch and return failure if not found

        success, result = self._set_notification(conn, services[TileBusService]['characteristics'][TileBusReceiveHeaderCharacteristic], True, timeout)
        if not success:
            return success, result

        return self._set_notification(conn, services[TileBusService]['characteristics'][TileBusReceivePayloadCharacteristic], True, timeout)

    def _enable_streaming(self, conn, services, timeout=1.0):
        self._logger.info("Attempting to enable streaming")
        success, result = self._set_notification(conn, services[TileBusService]['characteristics'][TileBusStreamingCharacteristic], True, timeout)
        return success, result

    def _enable_tracing(self, conn, services, timeout=1.0):
        self._logger.info("Attempting to enable tracing")
        try:
            success, result = self._set_notification(conn, services[TileBusService]['characteristics'][TileBusTracingCharacteristic], True, timeout)
        except KeyError:
            return False, {'failure_reason': 'Tracing characteristic was not found in remote device\'s GATT table'}

        return success, result

    def _disable_rpcs(self, conn, services, timeout=1.0):
        """Prevent this device from receiving more RPCs."""

        success, result = self._set_notification(conn, services[TileBusService]['characteristics'][TileBusReceiveHeaderCharacteristic], False, timeout)
        if not success:
            return success, result

        return self._set_notification(conn, services[TileBusService]['characteristics'][TileBusReceivePayloadCharacteristic], False, timeout)

    def _enumerate_handles(self, conn, start_handle, end_handle, timeout=1.0):
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

        try:
            response = self._send_command(4, 3, payload)
            handle, result = unpack("<BH", response.payload)
        except InternalTimeoutError:
            return False, {'reason': "Timeout enumerating handles"}

        if result != 0:
            return False, None

        events = self._wait_process_events(timeout, event_filter_func, end_filter_func)
        handle_events = [x for x in events if event_filter_func(x)]

        attrs = {}
        for event in handle_events:
            process_attribute(attrs, event)

        return True, {'attributes': attrs}

    def _read_handle(self, conn, handle, timeout=1.0):
        conn_handle = conn
        payload = struct.pack("<BH", conn_handle, handle)

        try:
            response = self._send_command(4, 4, payload)
            ignored_handle, result = unpack("<BH", response.payload)
        except InternalTimeoutError:
            return False, {'reason': 'Timeout sending read handle command'}

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

    def _write_handle(self, conn, handle, ack, value, timeout=1.0):
        """Write to a BLE device characteristic by its handle.

        Args:
            conn (int): The connection handle for the device we should read from
            handle (int): The characteristics handle we should read
            ack (bool): Should this be an acknowledges write or unacknowledged
            timeout (float): How long to wait before failing
            value (bytearray): The value that we should write
        """

        conn_handle = conn
        char_handle = handle

        def write_handle_acked(event):
            if event.command_class == 4 and event.command == 1:
                conn, _, char = unpack("<BHH", event.payload)

                return conn_handle == conn and char_handle == char

        data_len = len(value)
        if data_len > 20:
            return False, {'reason': 'Data too long to write'}

        payload = struct.pack("<BHB%ds" % data_len, conn_handle, char_handle, data_len, value)

        try:
            if ack:
                response = self._send_command(4, 5, payload)
            else:
                response = self._send_command(4, 6, payload)
        except InternalTimeoutError:
            return False, {'reason': 'Timeout waiting for response to command in _write_handle'}

        _, result = unpack("<BH", response.payload)
        if result != 0:
            return False, {'reason': 'Error writing to handle', 'error_code': result}

        if ack:
            events = self._wait_process_events(timeout, lambda x: False, write_handle_acked)
            if len(events) == 0:
                return False, {'reason': 'Timeout waiting for acknowledge on write'}

            _, result, _ = unpack("<BHH", events[0].payload)
            if result != 0:
                return False, {'reason': 'Error received during write to handle', 'error_code': result}

        return True, None

    def _send_script(self, conn, services, data, curr_loc, progress_callback):
        hschar = services[TileBusService]['characteristics'][TileBusHighSpeedCharacteristic]['handle']

        chunk_size = 20
        if len(data) - curr_loc < 20:
            chunk_size = len(data) - curr_loc

        chunk = data[curr_loc:curr_loc+chunk_size]
        success, reason = self._write_handle(conn, hschar, False, chunk)

        if not success:
            if 'error_code' in reason and reason['error_code'] == 0x182: #If we are streaming too fast, back off and try again
                time.sleep(0.1)
                self.async_command(['_send_script', conn, services, data, curr_loc, progress_callback], self._current_callback, self._current_context)
                return True, None, True
            else:
                return False, reason

        progress_callback(curr_loc // 20, len(data) // 20)

        if curr_loc + chunk_size != len(data):
            self.async_command(['_send_script', conn, services, data, curr_loc+chunk_size, progress_callback], self._current_callback, self._current_context)
            return True, None, True

        return True, None

    def _send_rpc(self, conn, services, address, rpc_id, payload, timeout=5.0):
        header_char = services[TileBusService]['characteristics'][TileBusSendHeaderCharacteristic]
        payload_char = services[TileBusService]['characteristics'][TileBusSendPayloadCharacteristic]
        receive_header = services[TileBusService]['characteristics'][TileBusReceiveHeaderCharacteristic]['handle']
        receive_payload = services[TileBusService]['characteristics'][TileBusReceivePayloadCharacteristic]['handle']

        length = len(payload)

        if len(payload) < 20:
            payload += b'\x00'*(20 - len(payload))

        if len(payload) > 20:
            return False, {'reason': 'Payload is too long, must be at most 20 bytes'}

        header = bytearray([length, 0, rpc_id & 0xFF, (rpc_id >> 8) & 0xFF, address])

        if length > 0:
            result, value = self._write_handle(conn, payload_char['handle'], False, bytes(payload))
            if result is False:
                return result, value

        result, value = self._write_handle(conn, header_char['handle'], False, bytes(header))
        if result is False:
            return result, value

        #Now receive the tilebus response which is notified to us on two characteristics
        #If the device disconnected as a result of the rpc, then we will not see a notified
        #header but instead a disconnection event so process that as well.

        def notified_header(event):
            if event.command_class == 4 and event.command == 5:
                event_handle, att_handle = unpack("<BH", event.payload[0:3])
                return event_handle == conn and att_handle == receive_header
            elif event.command_class == 3 and event.command == 4:
                event_handle, reason = unpack("<BH", event.payload)
                return event_handle == conn

        def notified_payload(event):
            if event.command_class == 4 and event.command == 5:
                event_handle, att_handle = unpack("<BH", event.payload[0:3])
                return event_handle == conn and att_handle == receive_payload

        events = self._wait_process_events(timeout, lambda x: False, notified_header)
        if len(events) == 0:
            return False, {'reason': 'Timeout waiting for notified RPC response header'}
        elif events[0].command_class == 3 and events[0].command == 4:
            return True, {'status': 0xFF, 'length': 0, 'payload': '\x00'*20, 'disconnected': True}

        #Process the received RPC header
        _, resp_header = process_notification(events[0])

        status = resp_header[0]
        length = resp_header[3]

        if length > 0:
            events = self._wait_process_events(timeout, lambda x: False, notified_payload)
            if len(events) == 0:
                return False, {'reason': 'Timeout waiting for notified RPC response payload'}

            _, resp_payload = process_notification(events[0])
        else:
            resp_payload = b'\x00'*20

        return True, {'status': status, 'length': length, 'payload': resp_payload, 'disconnected': False}

    def _set_advertising_data(self, packet_type, data):
        """Set the advertising data for advertisements sent out by this bled112.

        Args:
            packet_type (int): 0 for advertisement, 1 for scan response
            data (bytearray): the data to set
        """

        payload = struct.pack("<BB%ss" % (len(data)), packet_type, len(data), bytes(data))
        response = self._send_command(6, 9, payload)

        result, = unpack("<H", response.payload)
        if result != 0:
            return False, {'reason': 'Error code from BLED112 setting advertising data', 'code': result}

        return True, None

    def _set_mode(self, discover_mode, connect_mode):
        """Set the mode of the BLED112, used to enable and disable advertising.

        To enable advertising, use 4, 2.
        To disable advertising use 0, 0.

        Args:
            discover_mode (int): The discoverability mode, 0 for off, 4 for on (user data)
            connect_mode (int): The connectability mode, 0 for of, 2 for undirected connectable
        """

        payload = struct.pack("<BB", discover_mode, connect_mode)
        response = self._send_command(6, 1, payload)

        result, = unpack("<H", response.payload)
        if result != 0:
            return False, {'reason': 'Error code from BLED112 setting mode', 'code': result}

        return True, None

    def _send_notification(self, handle, value):
        """Send a notification to all connected clients on a characteristic.

        Args:
            handle (int): The handle we wish to notify on
            value (bytearray): The value we wish to send
        """

        value_len = len(value)
        value = bytes(value)

        payload = struct.pack("<BHB%ds" % value_len, 0xFF, handle, value_len, value)

        response = self._send_command(2, 5, payload)
        result, = unpack("<H", response.payload)
        if result != 0:
            return False, {'reason': 'Error code from BLED112 notifying a value', 'code': result, 'handle': handle, 'value': value}

        return True, None

    def _set_notification(self, conn, char, enabled, timeout=1.0):
        """Enable/disable notifications on a GATT characteristic.

        Args:
            conn (int): The connection handle for the device we should interact with
            char (dict): The characteristic we should modify
            enabled (bool): Should we enable or disable notifications
            timeout (float): How long to wait before failing
        """

        if 'client_configuration' not in char:
            return False, {'reason': 'Cannot enable notification without a client configuration attribute for characteristic'}

        props = char['properties']
        if not props.notify:
            return False, {'reason': 'Cannot enable notification on a characteristic that does not support it'}

        value = char['client_configuration']['value']

        #Check if we don't have to do anything
        current_state = bool(value & (1 << 0))
        if current_state == enabled:
            return

        if enabled:
            value |= 1 << 0
        else:
            value &= ~(1 << 0)

        char['client_configuration']['value'] = value

        valarray = struct.pack("<H", value)
        return self._write_handle(conn, char['client_configuration']['handle'], True, valarray, timeout)

    def _connect(self, address):
        """Connect to a device given its uuid."""

        latency = 0
        conn_interval_min = 6
        conn_interval_max = 100
        timeout = 1.0

        try:
            #Allow passing either a binary address or a hex string
            if isinstance(address, str) and len(address) > 6:
                address = address.replace(':', '')
                address = bytes(bytearray.fromhex(address)[::-1])
        except ValueError:
            return False, None

        #Allow simple determination of whether a device has a public or private address
        #This is not foolproof
        private_bits = bytearray(address)[-1] >> 6
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
        formatted_addr = ":".join(["%02X" % x for x in bytearray(addr)])
        self._logger.info('Connected to device %s with interval=%d, timeout=%d, latency=%d',
                          formatted_addr, interval, timeout, latency)

        connection = {"handle": handle}
        return True, connection

    def _disconnect(self, handle):
        """Disconnect from a device that we have previously connected to."""

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
        """Send a BGAPI packet to the dongle and return the response."""

        if len(payload) > 60:
            return ValueError("Attempting to send a BGAPI packet with length > 60 is not allowed", actual_length=len(payload), command=command, command_class=cmd_class)

        header = bytearray(4)
        header[0] = 0
        header[1] = len(payload)
        header[2] = cmd_class
        header[3] = command

        packet = header + bytearray(payload)
        self._stream.write(bytes(packet))

        #Every command has a response so wait for the response here
        response = self._receive_packet(timeout)
        return response

    def event_handler(self, event_packet):
        self._loop.run_coroutine(self.operations.process_message, event_packet, wait=False)

    def _receive_packet(self, timeout=3.0):
        """Receive a response packet to a command."""

        while True:
            response_data = self._stream.read_packet(timeout=timeout)
            response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

            if response.is_event:
                if self.event_handler is not None:
                    self.event_handler(response)

                continue

            return response

    def stop(self):
        """Stop this background command processor."""

        self._commands.put(None)
        self.join()

    def async_command(self, cmd, callback, context):
        self._commands.put((cmd, callback, False, context))

    async def future_command(self, cmd):
        """Run command as a coroutine and return a future.

        Args:
            loop (BackgroundEventLoop): The loop that we should attach
                the future too.
            cmd (list): The command and arguments that we wish to call.

        Returns:
            asyncio.Future: An awaitable future with the result of the operation.
        """

        if self._asyncio_cmd_lock is None:
            raise HardwareError("Cannot use future_command because no event loop attached")

        async with self._asyncio_cmd_lock:
            return await self._future_command_unlocked(cmd)

    def _future_command_unlocked(self, cmd):
        """Run command as a coroutine and return a future.

        Args:
            loop (BackgroundEventLoop): The loop that we should attach
                the future too.
            cmd (list): The command and arguments that we wish to call.

        Returns:
            asyncio.Future: An awaitable future with the result of the operation.
        """

        future = self._loop.create_future()
        asyncio_loop = self._loop.get_loop()

        def _done_callback(result):
            retval = result['return_value']

            if not result['result']:
                future.set_exception(HardwareError("Error executing synchronous command",
                                                   command=cmd, return_value=retval))
            else:
                future.set_result(retval)

        callback = functools.partial(asyncio_loop.call_soon_threadsafe, _done_callback)
        self._commands.put((cmd, callback, True, None))

        return future

    def _process_events(self, return_filter=None, max_events=0):
        to_return = []
        try:
            while True:
                event_data = self._stream.queue.get_nowait()
                event = BGAPIPacket(is_event=(event_data[0] == 0x80), command_class=event_data[2],
                                    command=event_data[3], payload=event_data[4:])

                if not event.is_event:
                    self._logger.error('Received response when we should have only received events, %s',event)
                elif return_filter is not None and return_filter(event):
                    to_return.append(event)
                elif self.event_handler is not None:
                    self.event_handler(event)
                else:
                    self._logger.info("Dropping event that had no evnt handler: %s", event)

                if max_events > 0 and len(to_return) == max_events:
                    return to_return
        except Empty:
            pass

        return to_return

    def _wait_process_events(self, total_time, return_filter, end_filter):
        """Synchronously process events until a specific event is found or we timeout.

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

        start_time = time.time()
        end_time = start_time + total_time

        while time.time() < end_time:
            events = self._process_events(lambda x: return_filter(x) or end_filter(x), max_events=1)
            acc += events

            for event in events:
                if end_filter(event):
                    return acc

            if len(events) == 0:
                time.sleep(delta)

        return acc
