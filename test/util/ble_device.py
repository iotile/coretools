import struct
import uuid

class MockBLEDevice (object):
    """A mock BLE device that can be scanned and connected to
    """

    ConnectableAdvertising = 0x00
    NonconnectableAdvertising = 0x02
    ScanResponsePacket = 0x04

    EarlyDisconnect = 1

    def __init__(self, mac, error, rssi=-50):
        self.services = {}
        self.mac = mac
        self.rssi = rssi
        self.simulate_error = error
        self._next_handle = 1
        self.handles = {}
        self.values = {}

    def add_char(self, service_id, char_id, can_notify):
        handle = self._next_handle
        self._next_handle += 1

        if service_id not in self.services:
            self.services[service_id] = {}

        service = self.services[service_id]

        val = (handle, 'char')
        if char_id not in service:
            service[char_id] = []

        char = service[char_id]
        char.append(val)
        self.handles[handle] = val

        #Add in the value of this characteristic declaration
        self.values[handle] = self._make_char_decl({'uuid': char_id, 'value_handle': handle+1, 'properties': int(can_notify) << 4})

        handle = self._next_handle
        self._next_handle += 1

        val = (handle, 'value')
        char.append(val)
        self.handles[handle] = val

        if can_notify:
            handle = self._next_handle
            self._next_handle += 1

            val = (handle, 'config')
            char.append(val)
            self.handles[handle] = val
            self.values[handle] = struct.pack("<H", 0)

    def _make_char_decl(self, info):
        uuid_bytes = info['uuid'].bytes_le
        handle = info['value_handle']
        props = info['properties']

        return struct.pack("<BH%ds" % len(uuid_bytes), props, handle, uuid_bytes)

    def find_uuid(self, handle):
        for serv_uuid, serv  in self.services.iteritems():
            for char_uuid, handles in serv.iteritems():
                for iterhandle,handle_type in handles:
                    if iterhandle == handle:
                        return char_uuid

        raise ValueError("Could not find UUID for handle %d" % handle)

    def find_handle(self, uuid, desired_type='value'):
        for serv_uuid, serv  in self.services.iteritems():
            for char_uuid, handles in serv.iteritems():
                if char_uuid != uuid:
                    continue

                for iterhandle,handle_type in handles:
                    if handle_type == desired_type:
                        return iterhandle

        raise ValueError("Could not find handle by UUID: %s" % str(uuid))

    @property
    def gatt_services(self):
        return self.services.keys()

    def iter_handles(self, start, end):
        for key, val in self.handles.iteritems():
            if key >= start and key <= end:
                yield val

    def min_handle(self, service):
        return min([min(x, key=lambda y: y[0]) for x in self.services[service].itervalues()])[0]

    def max_handle(self, service):
        return max([max(x, key=lambda y: y[0]) for x in self.services[service].itervalues()])[0]

    @property
    def advertisement_type(self): 
        return self.NonconnectableAdvertising

    def advertisement(self):
        return bytearray(31)

    def scan_response(self):
        return bytearray(31)

    def read_handle(self, handle):
        if handle in self.values:
            return self.values[handle]

        #FIXME: Actually ask the subclass for the handle value here
        return bytearray(20)

    def write_handle(self, handle, value):
        if handle in self.values:
            self.values[handle] = value
            return True, []

        handle_id = self.find_uuid(handle)
        return self._handle_write(handle_id, value)

    def notifications_enabled(self, handle_id):
        handle = self.find_handle(handle_id, 'config')
        value, = struct.unpack("<H", self.values[handle])

        if value & 0b1:
            return True

        return False

class MockIOTileDevice(MockBLEDevice):
    TBService = uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')
    TBSendHeaderChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000320')
    TBSendPayloadChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000420')
    TBReceiveHeaderChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000120')
    TBReceivePayloadChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000220')
    TBStreamingChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000520')
    TBHighSpeedChar = uuid.UUID('fb349b5f-8000-0080-0010-000000000620')

    ArchManuID = 0x03C0

    def __init__(self, iotile_id, mac, voltage, error):
        super(MockIOTileDevice, self).__init__(mac, error)

        self.voltage = voltage
        self.pending_data = False
        self.user_connected = False
        self.iotile_id = iotile_id

        self.rpc_payload = bytearray(20)

        self.add_char(self.TBService, self.TBSendHeaderChar, False)
        self.add_char(self.TBService, self.TBSendPayloadChar, False)
        self.add_char(self.TBService, self.TBReceiveHeaderChar, True)
        self.add_char(self.TBService, self.TBReceivePayloadChar, True)
        self.add_char(self.TBService, self.TBStreamingChar, True)
        self.add_char(self.TBService, self.TBHighSpeedChar, False)

    @property
    def low_voltage(self):
        return self.voltage < 3.2

    @property
    def advertisement_type(self):
        if self.user_connected:
            return MockBLEDevice.NonconnectableAdvertising
        else:
            return MockBLEDevice.ConnectableAdvertising

    def advertisement(self):
        flags = (int(self.low_voltage) << 1) | (int(self.user_connected) << 2) | (int(self.pending_data))
        ble_flags = struct.pack("<BBB", 2, 0, 0) #FIXME fix length
        uuid_list = struct.pack("<BB16s", 17, 6, self.TBService.bytes_le)
        manu = struct.pack("<BBHLH", 9, 0xFF, self.ArchManuID, self.iotile_id, flags)

        return ble_flags + uuid_list + manu

    def scan_response(self):
        header = struct.pack("<BBH", 19, 0xFF, self.ArchManuID)
        voltage = struct.pack("<H", int(self.voltage*256))
        reading = struct.pack("<HLLL", 0xFFFF, 0, 0, 0)
        name = struct.pack("<BB6s", 7, 0x09, "IOTile")
        reserved = struct.pack("<BBB", 0, 0, 0)

        response = header + voltage + reading + name + reserved
        assert len(response) == 31

        return response

    def _handle_rpc(self, address, rpc_id, payload):
        return 0xFF, bytearray()

    def _handle_write(self, char_id, value):
        if char_id == self.TBSendPayloadChar:
            self.rpc_payload = value
            return True, []

        #Check if we should trigger an RPC
        if char_id == self.TBSendHeaderChar:
            length, _, cmd, feature, address = struct.unpack("<BBBBB", str(value))
            rpc_id = (feature << 8) |  cmd

            resp_status, resp_payload = self._handle_rpc(address, rpc_id, self.rpc_payload[:length])
            resp_header = struct.pack("<BBBB", resp_status, 0, len(resp_payload), 0)

            if len(resp_payload) > 0:
                return True, [(self.find_handle(self.TBReceivePayloadChar), resp_payload), (self.find_handle(self.TBReceiveHeaderChar), resp_header)]
            else:
                return True, [(self.find_handle(self.TBReceiveHeaderChar), resp_header)]

        return False, []