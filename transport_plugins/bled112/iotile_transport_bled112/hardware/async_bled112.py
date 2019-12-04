"""A asyncio wrapper around a BLED112 dongle."""

import struct
import logging
import asyncio
from iotile.core.utilities.async_tools import SharedLoop, BackgroundEventLoop
from iotile.core.utilities.async_tools.operation_manager import MessageSpec, OperationManager
from iotile.core.hw.exceptions import DeviceAdapterError
from ..tilebus import *
from ..bgapi_structures import process_gatt_service, process_attribute, process_read_handle, process_notification
from ..bgapi_structures import parse_characteristic_declaration
from .async_packet import AsyncPacketReader


class _BLED112Locks:
    """Internal helper class to manage locks."""

    def __init__(self, loop: BackgroundEventLoop):
        self._loop = loop

        self.cmd = loop.create_lock()
        self.mode = loop.create_lock()
        self._conn_locks = {}

    def conn(self, handle):
        """Obtain a lock for a given ble connection."""

        if handle not in self._conn_locks:
            self._conn_locks[handle] = self._loop.create_lock()

        return self._conn_locks[handle]


class BLEQueueFullError(DeviceAdapterError):
    """Error indicating a ble notification or write cannot be queued.

    The queue is temporarily full so the caller should sleep and retry
    in a few connection intervals (typically 10-50 ms per conn interval)
    """


class BLEDisconnectError(DeviceAdapterError):
    """The BLE device unexpected disconnected during the operation."""


class AsyncBLED112:
    """A coroutine based API on top of the BLED112 dongle.

    This class is designed for INTERNAL USE only and is not considered
    public or stable.  It is meant as a helper class to implement a
    DeviceAdapter and a DeviceServer on top of bled112 hardware.

    Args:
        serial (serial.Serial):  The serial port connected to the bled112
            dongle.
        loop (BackgroundEventLoop): The loop we should run in.
    """

    def __init__(self, serial, loop=SharedLoop):
        self._serial = serial
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())

        self.operations = OperationManager(loop=loop)

        self._loop = loop
        self._locks = _BLED112Locks(loop)
        self._reader = AsyncPacketReader(self._serial, self.operations.queue_message_threadsafe)

    async def set_scan_parameters(self, interval=2100, window=2100, active=False):
        """Set the scan parameters like interval and window in units of ms."""

        active_num = 0
        if bool(active):
            active_num = 1

        interval_num = int(interval*1000/625)
        window_num = int(window*1000/625)

        payload = struct.pack("<HHB", interval_num, window_num, active_num)

        await self.send_command_locked(6, 7, payload, check=True)

    async def query_systemstate(self):
        """Query the maximum number of connections supported by this adapter."""

        async with self._locks.cmd:
            response = await self._send_command_unlocked(0, 6, [], pause=True)

            try:
                maxconn, = struct.unpack("<B", response.payload)
                spec = MessageSpec(class_=3, cmd=0, event=True)
            except:
                self.operations.unpause()
                raise

            events = await self.operations.gather_count([spec], maxconn, timeout=3, unpause=True)

        conns = []
        for event in events:
            handle, flags, _addr, _addr_type, _interval, _timeout, _lat, _bond = struct.unpack("<BB6sBHHHB", event.payload)

            if flags != 0:
                conns.append(handle)

        return {'max_connections': maxconn, 'active_connections': conns}

    async def start_scan(self, active):
        """Begin scanning forever."""

        if self._locks.mode.locked():
            raise DeviceAdapterError(None, 'start_scan', 'another operation is in progress (like connect)')

        async with self._locks.mode:
            await self.set_scan_parameters(active=active)
            await self.send_command_locked(6, 2, [2], check=True)

    async def stop_scan(self):
        """Stop scanning for BLE devices."""

        await self.send_command_locked(6, 4, [], check=True)

    async def probe_services(self, handle):
        """Probe for all primary services and characteristics in those services.

        Args:
            handle (int): the connection handle to probe
        """

        end_spec = MessageSpec(class_=4, cmd=1, conn=handle)
        gatt_spec = MessageSpec(class_=4, cmd=2, conn=handle)
        payload = struct.pack('<BHHBH', handle, 1, 0xFFFF, 2, 0x2800)

        async with self._locks.conn(handle):
            await self.send_command_locked(4, 1, payload, pause=True, check="<xH")
            events = await self.operations.gather_until([gatt_spec, end_spec], end_spec, timeout=2.0, unpause=True)

        end_event = events[-1]
        gatt_events = events[:-1]

        #Make sure we successfully probed the gatt table
        _, result, _ = struct.unpack("<BHH", end_event.payload)
        if result != 0:
            self._logger.warning("Error enumerating GATT table, protocol error code = %d (0x%X)", result, result)
            return False, None

        services = {}
        for event in gatt_events:
            process_gatt_service(services, event)

        return {'services': services}

    async def probe_characteristics(self, conn, services, timeout=5.0):
        """Probe gatt services for all associated characteristics in a BLE device.

        Args:
            conn (int): the connection handle to probe
            services (dict): a dictionary of services produced by probe_services()
            timeout (float): the maximum number of seconds to spend in any single task
        """

        for service in services.values():
            result = await self._enumerate_handles(conn, service['start_handle'], service['end_handle'])

            attributes = result['attributes']

            service['characteristics'] = {}

            last_char = None
            for handle, attribute in attributes.items():
                if attribute['uuid'].hex[-4:] == '0328':
                    result = await self._read_handle(conn, handle, timeout)

                    value = result['data']
                    char = parse_characteristic_declaration(value)
                    service['characteristics'][char['uuid']] = char
                    last_char = char
                elif attribute['uuid'].hex[-4:] == '0229':
                    if last_char is None:
                        raise DeviceAdapterError(None, 'probe_characteristics',
                                                 'invalid gatt table that was not ordered correctly')

                    result = await self._read_handle(conn, handle, timeout)

                    value = result['data']
                    assert len(value) == 2
                    value, = struct.unpack("<H", value)

                    last_char['client_configuration'] = {'handle': handle, 'value': value}

        return {'services': services}

    async def write_highspeed(self, conn, handle, data, progress_callback=None):
        i = 0
        while i < len(data):
            chunk = data[i:i + 20]

            try:
                await self._write_handle(conn, handle, False, chunk)

                if progress_callback is not None:
                    progress_callback(i // 20, len(data) // 20)

                i += 20
            except BLEQueueFullError:
                await asyncio.sleep(0.1)

    async def set_advertising_data(self, packet_type, data):
        """Set the advertising data for advertisements sent out by this bled112.

        Args:
            packet_type (int): 0 for advertisement, 1 for scan response
            data (bytearray): the data to set
        """

        payload = struct.pack("<BB%ss" % (len(data)), packet_type, len(data), bytes(data))
        await self.send_command_locked(6, 9, payload, check="<H")

    async def set_mode(self, discover_mode, connect_mode):
        """Set the mode of the BLED112, used to enable and disable advertising.

        To enable advertising, use 4, 2.
        To disable advertising use 0, 0.

        Args:
            discover_mode (int): The discoverability mode, 0 for off, 4 for on (user data)
            connect_mode (int): The connectability mode, 0 for of, 2 for undirected connectable
        """

        payload = struct.pack("<BB", discover_mode, connect_mode)
        await self.send_command_locked(6, 1, payload, check="<H")

    async def send_notification(self, handle, value):
        """Send a notification to all connected clients on a characteristic.

        Args:
            handle (int): The handle we wish to notify on
            value (bytearray): The value we wish to send
        """

        value_len = len(value)
        value = bytes(value)

        payload = struct.pack("<BHB%ds" % value_len, 0xFF, handle, value_len, value)
        resp = await self.send_command_locked(2, 5, payload)
        result, = struct.unpack("<H", resp.payload)
        if result == 0x182:
            raise BLEQueueFullError(None, 'send_notification', 'Queue full, need to backoff and retry')
        if result == 0x181:
            raise BLEDisconnectError(None, 'send_notification', 'Device disconnected before write completed')
        if result != 0:
            raise DeviceAdapterError(None, 'send_notification', 'Error received (error=0x%x)' % result)

    async def set_notification(self, conn, char, enabled, timeout=1.0):
        """Enable/disable notifications on a GATT characteristic.

        Args:
            conn (int): The connection handle for the device we should interact with
            char (dict): The characteristic we should modify
            enabled (bool): Should we enable or disable notifications
            timeout (float): How long to wait before failing
        """

        if 'client_configuration' not in char:
            raise DeviceAdapterError(None, 'set_notification', 'cannot enable notification without a client configuration attribute for characteristic')

        props = char['properties']
        if not props.notify:
            raise DeviceAdapterError(None, 'set_notification', 'cannot enable notification on a characteristic that does not support it')

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
        await self._write_handle(conn, char['client_configuration']['handle'], True, valarray, timeout)

    async def connect(self, address):
        """Connect to a device given its mac address."""

        latency = 0
        conn_interval_min = 6
        conn_interval_max = 100
        timeout = 1.0

        address, address_type = _convert_address(address)

        payload = struct.pack("<6sBHHHH", address, address_type, conn_interval_min,
                              conn_interval_max, int(timeout*100.0), latency)

        async with self._locks.mode:
            response = await self.send_command_locked(6, 3, payload, pause=True, check="<H")
            _, handle = struct.unpack("<HB", response.payload)

            try:
                event = await self.operations.wait_for(class_=3, cmd=0, conn=handle, timeout=4.0, unpause=True)
            except:
                await self.stop_scan()
                raise

        handle, _, addr, _, interval, timeout, latency, _ = struct.unpack("<BB6sBHHHB", event.payload)
        formatted_addr = ":".join(["%02X" % x for x in bytearray(addr)])
        self._logger.info('Connected to device %s with interval=%d, timeout=%d, latency=%d',
                          formatted_addr, interval, timeout, latency)

        return handle

    async def disconnect(self, handle):
        """Disconnect from a device that we have previously connected to."""

        payload = struct.pack('<B', handle)

        async with self._locks.conn(handle):
            await self.send_command_locked(3, 0, payload, pause=True, check="<xH")
            await self.operations.wait_for(class_=3, cmd=4, conn=handle, timeout=4.0, unpause=True)

    async def send_command_locked(self, cmd_class, command, payload, *, pause=False, check=False, timeout=3.0):
        async with self._locks.cmd:
            return await self._send_command_unlocked(cmd_class, command, payload, timeout=timeout,
                                                     check=check, pause=pause)

    async def stop(self):
        """Stop this background command processor."""

        await self._loop.run_in_executor(self._reader.stop)

    async def _send_command_unlocked(self, cmd_class, command, payload, *, timeout=3.0, pause=False, check=False):
        """Send a BGAPI packet to the dongle and return the response."""

        if not isinstance(payload, (bytes, bytearray)):
            payload = bytes(payload)

        if len(payload) > 60:
            return ValueError("Attempting to send a BGAPI packet with length > 60 is not allowed",
                              actual_length=len(payload), command=command, command_class=cmd_class)

        packet = struct.pack("<BBBB%ds" % len(payload), 0, len(payload), cmd_class, command, payload)

        self.operations.pause()

        try:
            self._serial.write(packet)
        except:
            self.operations.unpause()
            raise

        result = await self.operations.wait_for(timeout, unpause=True, pause=pause,
                                                class_=cmd_class, cmd=command)

        if isinstance(check, str) or check is True:
            format_string = "<B"
            if isinstance(check, str):
                format_string = check

            error, = struct.unpack_from(format_string, result.payload)
            if error != 0:
                if pause:
                    self.operations.unpause()

                raise DeviceAdapterError(None, 'bled112 command (%d, %d)' % (cmd_class, command),
                                         'error code %d (0x%X)' % (error, error))

        return result

    async def _write_handle(self, conn, handle, ack, value, timeout=1.0):
        """Write to a BLE device characteristic by its handle.

        Args:
            conn (int): The connection handle for the device we should read from
            handle (int): The characteristics handle we should read
            ack (bool): Should this be an acknowledges write or unacknowledged
            timeout (float): How long to wait before failing
            value (bytearray): The value that we should write
        """

        data_len = len(value)
        if data_len > 20:
            raise DeviceAdapterError(None, 'write_handle', 'Data too long to write')

        payload = struct.pack("<BHB%ds" % data_len, conn, handle, data_len, value)

        async with self._locks.conn(conn):
            if not ack:
                await self.send_command_locked(4, 5, payload, check="<xH")
                return

            await self.send_command_locked(4, 6, payload, check="<xH", pause=True)

            event, = self.operations.wait_for(class_=4, command=1, conn=conn, timeout=timeout, unpause=True)

        _, result, _ = struct.unpack("<BHH", event.payload)
        if result == 0x182:
            raise BLEQueueFullError(None, 'write_handle', 'Queue full, need to backoff and retry')
        if result == 0x181:
            raise BLEDisconnectError(None, 'write_handle', 'Device disconnected before write completed')
        if result != 0:
            raise DeviceAdapterError(None, 'write_handle', 'Error received (error=0x%x)' % result)

    async def _enumerate_handles(self, conn, start_handle, end_handle, timeout=1.0):
        payload = struct.pack("<BHH", conn, start_handle, end_handle)
        end_spec = MessageSpec(class_=4, cmd=1, conn=conn)
        handle_spec = MessageSpec(class_=4, cmd=4, conn=conn)

        async with self._locks.conn(conn):
            await self.send_command_locked(4, 3, payload, pause=True, check="<xH")
            events = await self.operations.gather_until([handle_spec], end_spec, timeout=timeout, unpause=True)

        attrs = {}
        for event in events:
            process_attribute(attrs, event)

        return {'attributes': attrs}

    async def _read_handle(self, conn, handle, timeout=1.0):
        payload = struct.pack("<BH", conn, handle)

        end_spec = MessageSpec(class_=4, cmd=1, conn=conn)
        handle_spec = MessageSpec(class_=4, cmd=5, conn=conn)

        async with self._locks.conn(conn):
            await self.send_command_locked(4, 4, payload, pause=True, check="<xH")
            event, = await self.operations.gather_count([handle_spec, end_spec], count=1, timeout=timeout, unpause=True)

        # We could have either gotten data or an error event, check if error and raise
        if event.cmd == 1:
            raise DeviceAdapterError(None, 'enumerate_handles', 'error reading handle')

        handle_type, handle_data = process_read_handle(event)
        return {'type': handle_type, 'data': handle_data}


def _convert_address(address):
    try:
        #Allow passing either a binary address or a hex string
        if isinstance(address, str) and len(address) > 6:
            address = address.replace(':', '')
            address = bytes(bytearray.fromhex(address)[::-1])
    except ValueError as err:
        raise DeviceAdapterError(None, 'connect', 'Error converting address') from err

    #Allow simple determination of whether a device has a public or private address
    #This is not foolproof
    private_bits = bytearray(address)[-1] >> 6
    if private_bits == 0b11:
        address_type = 1
    else:
        address_type = 0

    return address, address_type
