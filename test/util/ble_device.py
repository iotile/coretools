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
    
    @property
    def advertisement_type(self): 
        return self.NonconnectableAdvertising

    def advertisement(self):
        return bytearray(31)

    def scan_response(self):
        return bytearray(31)


class MockIOTileDevice(MockBLEDevice):
    TileBusService = uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')
    ArchManuID = 0x03C0

    def __init__(self, iotile_id, mac, voltage, error):
        super(MockIOTileDevice, self).__init__(mac, error)

        self.voltage = voltage
        self.pending_data = False
        self.user_connected = False
        self.iotile_id = iotile_id

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
        uuid_list = struct.pack("<BB16s", 17, 6, self.TileBusService.bytes_le)
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
