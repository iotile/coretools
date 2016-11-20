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
        make_event(3, 0): ["BBXBHHHB", ["handle", "flags", "address", "addr_type", "interval", "timeout", "latency", "bonding"]],
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
                val = val.decode('hex')
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
            arr_size = len(payload) - expected_size + 1
            fmt_code = fmt_code.replace('A', '%ds' % arr_size)

        data = struct.unpack("<" + fmt_code, payload)
        output = {fmt_names[index]: x for index, x in enumerate(data)}

        if addr_index >= 0:
            addr_name = fmt_names[addr_index]
            raw_addr = output[addr_name]
            output[addr_name] = ":".join(["{:02X}".format(ord(x)) for x in raw_addr])

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
        self._logger = logging.getLogger('mockbled112')

    def add_device(self, device):
        self.devices[device.mac] = device

    def _register_handlers(self):
        self.handlers = {}
        self.handlers[make_command(0, 6)] = self._handle_system_status
        self.handlers[make_command(6, 7)] = self._handle_set_scan_parameters
        self.handlers[make_command(6, 2)] = self._start_scan
        self.handlers[make_command(6, 4)] = self._end_procedure
        self.handlers[make_command(6, 3)] = self._connect
    
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

    def _handle_system_status(self, payload):
        packets = []
        packets.append({'type': (0, 6, False, True), 'max_connections': self.max_connections})

        for i in xrange(0, self.max_connections):
            packets.append({'handle': i, 'flags': 0, 'address': '00:00:00:00:00:00', 'addr_type': 0, "interval": 0, 
                            "timeout": 0, "latency": 0, "bonding": 0, 'type': bgapi_event(3, 0)})

        return packets

    def _handle_set_scan_parameters(self, payload):
        self.active_scan = bool(payload['active'])

        resp = {'type': bgapi_resp(6, 7), 'result': 0}
        return [resp]

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
            event = {'handle': len(self.connections), 'flags': 0xFF, 'address': addr, 'address_type': payload['addr_type'],
                     'interval': payload['interval_min'], 'timeout': payload['timeout'], latency: payload['latency'], 'bonding': 0xFF}

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
