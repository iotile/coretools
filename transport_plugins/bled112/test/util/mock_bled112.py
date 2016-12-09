import struct
import copy
import logging

def make_id(cmdclass, cmd, event, response=False):
    return (int(event) << 17 | int(response) << 16) | (cmdclass << 8) | cmd

def make_command(cmdclass, cmd):
    return make_id(cmdclass, cmd, False, False)

def make_event(cmdclass, cmd):
    return make_id(cmdclass, cmd, True, True)

def make_resp(cmdclass, cmd):
    return make_id(cmdclass, cmd, False, True)

def bgapi_event(cmdclass, cmd):
    return (cmdclass, cmd, True, True)

def bgapi_resp(cmdclass, cmd):
    return (cmdclass, cmd, False, True)    

class BGAPIPacket(object):
    formats = {
        #Disconnect
        make_command(3, 0): ["B", ["handle"]],
        make_resp(3, 0): ["BH", ["handle", "result"]],
        make_event(3, 4): ["BH", ["handle", "reason"]], #disconnected event

        #Connect
        make_command(6, 3): ["XBHHHH", ["address", "address_type", "interval_min", "interval_max", "timeout", "latency"]],
        make_resp(6, 3): ["HB", ["result", "handle"]],

        #Set scan parameters
        make_command(6, 7): ["HHB", ["interval", "window", "active"]],
        make_resp(6, 7): ["H", ["result"]],

        #Start scan
        make_command(6, 2): ["B", ["mode"]],
        make_resp(6, 2): ["H", ["result"]],
        make_event(6, 0): ["bBXBBA", ["rssi", "adv_type", "address", "address_type", "bond", "data"]],

        #End GAP procedure
        make_command(6, 4): [],
        make_resp(6, 4): ["H", ["result"]],

        #Get system status
        make_command(0, 6): [],
        make_resp(0, 6): ["B", ["max_connections"]], #system status response
        make_event(3, 0): ["BBXBHHHB", ["handle", "flags", "address", "address_type", "interval", "timeout", "latency", "bonding"]],

        #Query Gatt Table
        make_command(4, 1): ["BHHA", ["handle", "start_handle", "end_handle", "uuid"]],
        make_resp(4, 1): ["BH", ["handle", "result"]],
        make_event(4, 2): ["BHHA", ["handle", "start_handle", "end_handle", "uuid"]],
        make_event(4, 1): ["BHH", ["handle", "result", "end_char"]],

        #Enumerate Handles
        make_command(4, 3): ["BHH", ["handle", "start_handle", "end_handle"]],
        make_resp(4, 3): ["BH", ["handle", "result"]],
        make_event(4, 4): ["BHA", ["handle", "char_handle", "uuid"]],

        #Read Handles
        make_command(4, 4): ["BH", ["handle", "char_handle"]],
        make_resp(4, 4): ["BH", ["handle", "result"]],
        make_event(4, 5): ["BHBA", ["handle", "char_handle", "att_type", "value"]],

        #Write Handles
        make_command(4, 5): ["BHA", ["handle", "char_handle", "value"]],
        make_resp(4, 5): ["BH", ["handle", "result"]],

        #Write Command
        make_command(4, 6): ["BHA", ["handle", "char_handle", "value"]],
        make_resp(4, 6): ["BH", ["handle", "result"]]

    }

    def __init__(self, packet, response):
        header = packet[:4]
        flags, lenlow, cmdclass, cmd = struct.unpack('<BBBB', header)

        payload_len = ((flags & 0b11) << 8) | lenlow
        is_event = bool(flags & (1 << 7))

        self.event = is_event
        self.cmdclass = cmdclass
        self.cmd = cmd
        self.cmd_id = make_id(cmdclass, cmd, is_event, response)

        payload = packet[4:]
        assert len(payload) == payload_len

        self.payload = self._parse_payload(payload, self.formats[self.cmd_id])

    @classmethod
    def GeneratePacket(cls, info):
        cmdclass, cmd, event, resp = info['type']
        event = bool(event)
        cmd_id = make_id(cmdclass, cmd, event, resp)

        payload = cls.CreatePayload(cmd_id, info)
        header = struct.pack("<BBBB", int(event) << 7, len(payload), cmdclass, cmd)

        return header + payload

    @classmethod
    def CreatePayload(cls, cmd_id, info):
        fmt_codes, fmt_names = cls.formats[cmd_id]

        payload = bytearray()
        for i in xrange(0, len(fmt_codes)):
            code = fmt_codes[i]
            val = info[fmt_names[i]]
            if code == 'X':
                code = '6s'
                val = val.replace(':', '')
                val = val.decode('hex')[::-1]
            elif code == 'A':
                arrlen = len(val)
                code = '%ds' % (arrlen+1)
                val = str(bytearray([arrlen]) + val)

            data = struct.pack('<%s' % code, val)
            payload += data

        return payload

    def _parse_payload(self, payload, fmt):
        if len(fmt) == 0:
            return {}

        fmt_code = fmt[0]
        fmt_names = fmt[1]

        size_map = {'B': 1, 'b': 1, 'H': 2, 'L': 4, 'X': 6, 'A':0}
        expected_size = sum([size_map[x] for x in fmt_code])

        addr_index = -1
        arr_index = -1

        #Check for mac address
        if fmt_code.find('X') >= 0:
            addr_index = fmt_code.find('X')
            fmt_code = fmt_code.replace('X', '6s')
        
        #Check for array
        if fmt_code.find('A') >= 0:
            arr_index = fmt_code.find('A')
            arr_size = len(payload) - expected_size
            fmt_code = fmt_code.replace('A', '%ds' % arr_size)

        data = struct.unpack("<" + fmt_code, payload)
        output = {fmt_names[index]: x for index, x in enumerate(data)}

        if addr_index >= 0:
            addr_name = fmt_names[addr_index]
            raw_addr = output[addr_name]
            output[addr_name] = ":".join(["{:02X}".format(ord(x)) for x in raw_addr[::-1]])

        if arr_index >= 0:
            arr_name = fmt_names[arr_index]
            raw_array = output[arr_name]
            output[arr_name] = raw_array[1:]
        
        return output


class MockBLED112(object):
    def __init__(self, max_connections):
        self._register_handlers()
        self.devices = {}
        self.max_connections = max_connections
        self.connections =[]
        self.active_scan = False
        self.scanning = False
        self.connecting = False
        self._logger = logging.getLogger('mock.bled112')

    def add_device(self, device):
        self.devices[device.mac] = device

    def _register_handlers(self):
        self.handlers = {}
        self.handlers[make_command(0, 6)] = self._handle_system_status
        self.handlers[make_command(6, 7)] = self._handle_set_scan_parameters
        self.handlers[make_command(6, 2)] = self._start_scan
        self.handlers[make_command(6, 4)] = self._end_procedure
        self.handlers[make_command(6, 3)] = self._connect
        self.handlers[make_command(4, 1)] = self._find_by_group_type
        self.handlers[make_command(3, 0)] = self._disconnect
        self.handlers[make_command(4, 3)] = self._enumerate_handles
        self.handlers[make_command(4, 4)] = self._read_handle
        self.handlers[make_command(4, 5)] = self._write_handle
        self.handlers[make_command(4, 6)] = self._write_command
    
    def generate_response(self, packetdata):
        try:
            packet = BGAPIPacket(packetdata, False)
        except KeyError:
            return ""

        if packet.cmd_id not in self.handlers:
            raise ValueError("Unknown command code passed: 0x%X" % packet.cmd_id)

        handler = self.handlers[packet.cmd_id]
        responses = handler(packet.payload)
        
        out_packets = [BGAPIPacket.GeneratePacket(resp) for resp in responses]

        return "".join([str(x) for x in out_packets])

    def _read_handle(self, payload):
        handle = payload['handle']

        if handle > len(self.connections):
            resp = {'type': bgapi_resp(4, 4), 'handle': handle, 'result': 0x186} #0x186 is handle not connected
            return [resp]

        packets = []
        resp = {'type': bgapi_resp(4, 4), 'handle': handle, 'result': 0}
        packets.append(resp)

        dev = self.devices[self.connections[handle]]

        char_handle = payload['char_handle']

        event = {}
        event['type'] = bgapi_event(4, 5)
        event['handle'] = handle
        event['char_handle'] = char_handle
        event['att_type'] = 0 #Value was read
        event['value'] = dev.read_handle(char_handle)

        packets.append(event)

        #FIXME If we can't read the handle value then send a different completed event
        return packets

    def _write_handle(self, payload):
        handle = payload['handle']

        if handle > len(self.connections):
            resp = {'type': bgapi_resp(4, 5), 'handle': handle, 'result': 0x186} #0x186 is handle not connected
            return [resp]

        packets = []
        resp = {'type': bgapi_resp(4, 5), 'handle': handle, 'result': 0}
        packets.append(resp)

        dev = self.devices[self.connections[handle]]

        char_handle = payload['char_handle']

        success, notifications = dev.write_handle(char_handle, payload['value'])

        event = {}
        event['type'] = bgapi_event(4, 1)
        event['handle'] = handle
        event['end_char'] = char_handle
        
        if success:
            event['result'] = 0
        else:
            event['result'] = 0x0401

        packets.append(event)

        self._logger.info("Write on handle %d triggered %d notification(s)", char_handle, len(notifications))

        #If this write triggered any notifications, inject them
        for notification_handle, value in notifications:
            event = {}
            event['type'] = bgapi_event(4, 5)
            event['handle'] = handle
            event['char_handle'] = notification_handle
            event['att_type'] = 1 # Notified
            event['value'] = value
            packets.append(event)

        return packets

    def _write_command(self, payload):
        handle = payload['handle']

        if handle > len(self.connections):
            resp = {'type': bgapi_resp(4, 6), 'handle': handle, 'result': 0x186} #0x186 is handle not connected
            return [resp]

        packets = []
        resp = {'type': bgapi_resp(4, 6), 'handle': handle, 'result': 0}
        packets.append(resp)

        dev = self.devices[self.connections[handle]]
        char_handle = payload['char_handle']

        success, notifications = dev.write_handle(char_handle, payload['value'])

        #If this write triggered any notifications, inject them
        for notification_handle, value in notifications:
            event = {}
            event['type'] = bgapi_event(4, 5)
            event['handle'] = handle
            event['char_handle'] = notification_handle
            event['att_type'] = 1 # Notified
            event['value'] = value
            packets.append(event)

        return packets

    def _enumerate_handles(self, payload):
        handle = payload['handle']

        if handle > len(self.connections):
            resp = {'type': bgapi_resp(4, 3), 'handle': handle, 'result': 0x186} #0x186 is handle not connected
            return [resp]

        packets = []
        resp = {'type': bgapi_resp(4, 3), 'handle': handle, 'result': 0}
        packets.append(resp)

        dev = self.devices[self.connections[handle]]

        last_handle = 0xFFFF
        for chr_handle, chr_type in dev.iter_handles(payload['start_handle'], payload['end_handle']):
            if chr_type == 'char':
                event = {'type': bgapi_event(4, 4), 'handle': handle, 'char_handle': chr_handle, 'uuid': bytearray([0x03, 0x28])}
            elif chr_type == 'config':
                event = event = {'type': bgapi_event(4, 4), 'handle': handle, 'char_handle': chr_handle, 'uuid': bytearray([0x02, 0x29])}

            packets.append(event)

        end = {'type': bgapi_event(4, 1), 'handle': handle, 'result': 0, 'end_char': last_handle}
        packets.append(end)

        return packets

    def _find_by_group_type(self, payload):
        handle = payload['handle']

        if handle > len(self.connections):
            resp = {'type': bgapi_resp(4, 1), 'handle': handle, 'result': 0x186} #0x186 is handle not connected
            return [resp]

        packets = []
        resp = {'type': bgapi_resp(4, 1), 'handle': handle, 'result': 0}
        packets.append(resp)

        dev = self.devices[self.connections[handle]]
        services = dev.gatt_services

        #Send along all of the gatt services
        for service in services:
            min_handle = dev.min_handle(service)
            max_handle = dev.max_handle(service)

            serv_event = {'type': bgapi_event(4, 2), 'handle': handle, 'start_handle': min_handle, 'end_handle': max_handle, 'uuid': service.bytes_le}
            packets.append(serv_event)

        end = {'type': bgapi_event(4, 1), 'handle': handle, 'result': 0, 'end_char': 0xFFFF} #FIXME: Make this a real value
        packets.append(end)
        return packets

    def _handle_system_status(self, payload):
        packets = []
        packets.append({'type': (0, 6, False, True), 'max_connections': self.max_connections})

        for i in xrange(0, self.max_connections):
            packets.append({'handle': i, 'flags': 0, 'address': '00:00:00:00:00:00', 'address_type': 0, "interval": 0,
                            "timeout": 0, "latency": 0, "bonding": 0, 'type': bgapi_event(3, 0)})

        return packets

    def _handle_set_scan_parameters(self, payload):
        self.active_scan = bool(payload['active'])

        resp = {'type': bgapi_resp(6, 7), 'result': 0}
        return [resp]

    def _disconnect(self, payload):
        handle = payload['handle']
        packets = []

        if not (handle < len(self.connections)):
            resp = {'type': bgapi_resp(3, 0), 'handle': handle, 'result': 0x186}
            return [resp]

        resp = {'type': bgapi_resp(3, 0), 'handle': handle, 'result': 0}
        packets.append(resp)

        self.connections[handle] = None

        disc = {'type': bgapi_event(3, 4), 'handle': handle, 'reason': 0}
        packets.append(disc)
        return packets

    def _connect(self, payload):
        packets = []

        addr = payload['address']

        #If we're already connecting, fail
        if self.connecting:
            resp = {'type': bgapi_resp(6, 3), 'result': 0x181, 'handle': 0}
            return [resp]

        #Otherwise try to connect
        resp = {'type': bgapi_resp(6, 3), 'result': 0, 'handle': len(self.connections)}
        self.connecting = True
        
        packets.append(resp)
        
        if addr in self.devices:
            event = {'type': bgapi_event(3, 0), 'handle': len(self.connections), 'flags': 0xFF, 'address': addr, 'address_type': payload['address_type'],
                     'interval': payload['interval_min'], 'timeout': payload['timeout'], 'latency': payload['latency'], 'bonding': 0xFF}

            self.connections.append(addr)
            packets.append(event)

        return packets

    def _start_scan(self, payload):
        if self.scanning is True:
            resp = {'type': bgapi_resp(6, 2), 'result': 0x181} #Device in wrong state
        else:
            resp = {'type': bgapi_resp(6, 2), 'result': 0}
            self.scanning = True

        packets = self.advertise()

        return [resp] + packets

    def _end_procedure(self, payload):
        if self.scanning or self.connecting:
            resp = {'type': bgapi_resp(6, 4), 'result': 0}
            self.scanning = False
            self.connecting = False
        else:
            resp = {'type': bgapi_resp(6, 4), 'result': 0x181}

        return [resp]

    def advertise(self):
        """Send an advertising and scan response (if active scanning) for every attached device
        """

        if not self.scanning:
            return

        packets = []

        for mac, dev in self.devices.iteritems():
            packet = {}
            packet['type'] = bgapi_event(6, 0)
            packet['rssi'] = dev.rssi
            packet['adv_type'] = dev.advertisement_type
            packet['address'] = mac
            packet['address_type'] = 1 #Random address
            packet['bond'] = 0xFF #No bond
            packet['data'] = dev.advertisement()

            packets.append(packet)

            if self.active_scan:
                response = copy.deepcopy(packet)
                response['data'] = dev.scan_response()
                response['adv_type'] = dev.ScanResponsePacket
                packets.append(response)
        
        return packets
