"""
Mock a bled112 that generate a big amount of advertisement data
"""
import copy
import random
import struct
import datetime

from iotile.mock.mock_ble import MockBLEDevice
from iotile_transport_bled112.hardware.emulator.mock_bled112 import MockBLED112, BGAPIPacket, bgapi_resp, bgapi_event
from iotile.core.hw.reports import IOTileReading



def generate_mac():
    return "E6:0C:52:%02x:%02x:%02x" % \
        (random.randrange(256), random.randrange(256), random.randrange(256))


def generate_raw_time():
    cur_time = datetime.datetime.today().time()
    seconds_from_midnight = (cur_time.hour * 60 + cur_time.minute) * 60 + cur_time.second
    return seconds_from_midnight


def generate_random_reading():
    return IOTileReading(generate_raw_time(), random.randint(0, 0xFFFE), random.getrandbits(31))


def generate_iotile_id():
    return random.getrandbits(31)


def update_random_reading(reading, update_value_probability):
    reading.raw_time = generate_raw_time()
    if random.randint(0, 100) < update_value_probability:
        reading.value = random.getrandbits(31)


def generate_random_clients(unique_number, update_value_probability):
    generated_info = []

    for _ in range(unique_number):
        generated_info.append((generate_iotile_id(), generate_mac(), generate_random_reading()))

    while True:
        if generated_info:
            iotile_id, mac, reading = random.choice(generated_info)
            update_random_reading(reading, update_value_probability)

            yield (iotile_id, mac, reading)
        else:
            yield (generate_iotile_id(), generate_mac(), generate_random_reading())


class MockAdvertisingBLED112(MockBLED112):
    def __init__(self, max_connections):
        super().__init__(max_connections)

    def _start_scan(self, payload):
        if self.scanning is True:
            resp = {'type': bgapi_resp(6, 2), 'result': 0x181} #Device in wrong state
        else:
            resp = {'type': bgapi_resp(6, 2), 'result': 0}
            self.scanning = True

        return [resp]

    def advertisement(self, iotile_id, low_voltage=False, user_connected=False, device_reports=False):
        flags = (int(low_voltage) << 1) | (int(user_connected) << 2) | (int(device_reports))
        ble_flags = struct.pack("<BBB", 2, 0, 0) #FIXME fix length
        uuid_list = struct.pack("<BB16s", 17, 6, MockBLEDevice.TBService.bytes_le)
        manu = struct.pack("<BBHLH", 9, 0xFF, MockBLEDevice.ArchManuID, iotile_id, flags)

        return ble_flags + uuid_list + manu

    def scan_response(self, reading, voltage=3.5):
        header = struct.pack("<BBH", 19, 0xFF, MockBLEDevice.ArchManuID)
        voltage = struct.pack("<H", int(voltage*256))
        _reading = struct.pack("<HLLL", reading.stream, reading.value, reading.raw_time, 0)
        name = struct.pack("<BB6s", 7, 0x09, b"IOTile")
        reserved = struct.pack("<BBB", 0, 0, 0)

        response = header + voltage + _reading + name + reserved
        assert len(response) == 31

        return response


    def _generate_adv_response(self, info_generator):
        if not self.scanning:
            return

        packets = []

        next_iotile_id, next_mac, next_reading = next(info_generator)

        packet = {}
        packet['type'] = bgapi_event(6, 0)
        packet['rssi'] = random.randint(-103, -38)
        packet['adv_type'] = MockBLEDevice.NonconnectableAdvertising
        packet['address'] = next_mac
        packet['address_type'] = 1 #Random address
        packet['bond'] = 0xFF #No bond
        packet['data'] = self.advertisement(next_iotile_id)

        packets.append(packet)


        if self.active_scan:
            response = copy.deepcopy(packet)
            response['data'] = self.scan_response(next_reading)
            response['adv_type'] = MockBLEDevice.ScanResponsePacket

            packets.append(response)

        return packets

    def generate_multiple_adv_packets(self, number_of_packets=1, unique_number=1, update_value_probability=100):
        info_generator = generate_random_clients(unique_number, update_value_probability)

        while True:
            result = bytearray()
            for _ in range(number_of_packets):
                packets = self._generate_adv_response(info_generator)
                for packet in packets:
                    result.extend(BGAPIPacket.GeneratePacket(packet))

            yield result
