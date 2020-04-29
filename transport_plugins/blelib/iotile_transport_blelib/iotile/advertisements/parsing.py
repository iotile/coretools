"""This module contains functions for parsing of advertising packets"""

import datetime

from iotile.core.utilities.packed import unpack
from iotile_transport_blelib.iotile import IOTILE_SERVICE_UUID, TileBusService, ARCH_MANUFACTURER
from iotile_transport_blelib.interface import BLEAdvertisement #AbstractBLECentral, errors, messages,

def parse_v2_advertisement(advert: BLEAdvertisement):
    """ Parse the IOTile Specific advertisement packet"""

    # We have already verified that the device is an IOTile device
    # by checking its service data uuid in _process_scan_event so
    # here we just parse out the required information

    device_id, reboot_low, reboot_high_packed, flags, timestamp, \
    battery, counter_packed, broadcast_stream_packed, broadcast_value, \
    _mac = unpack("<LHBBLBBHLL", advert.service_data(IOTILE_SERVICE_UUID))

    reboots = (reboot_high_packed & 0xF) << 16 | reboot_low
    counter = counter_packed & ((1 << 5) - 1)
    broadcast_multiplex = counter_packed >> 5
    broadcast_toggle = broadcast_stream_packed >> 15
    broadcast_stream = broadcast_stream_packed & ((1 << 15) - 1)

    # Flags for version 2 are:
    #   bit 0: Has pending data to stream
    #   bit 1: Low voltage indication
    #   bit 2: User connected
    #   bit 3 - 5: Broadcast encryption key type
    #   bit 6: broadcast data is time synchronized to avoid leaking
    #   information about when it changes
    #   bit 7: Device is in Safe Mode
    is_pending_data = bool(flags & (1 << 0))
    is_low_voltage = bool(flags & (1 << 1))
    is_user_connected = bool(flags & (1 << 2))
    broadcast_encryption_key_type = (flags >> 3) & 7
    is_safe_mode = bool(flags & (1 << 7))

    info = {'connection_string': advert.sender,
            'uuid': device_id,
            'pending_data': is_pending_data,
            'low_voltage': is_low_voltage,
            'user_connected': is_user_connected,
            'safe_mode': is_safe_mode,
            'signal_strength': advert.rssi,
            'reboot_counter': reboots,
            'sequence': counter,
            'broadcast_toggle': broadcast_toggle, # FIX toggle is not decrypted at this point
            'timestamp': timestamp,
            'battery': battery / 32.0,
            'advertising_version':2}

    # TODO implement encryption
    payload = {
        'multiplex': broadcast_multiplex,
        'stream': broadcast_stream,
        'value': broadcast_value,
        'timestamp': timestamp
    }

    return info, payload

def parse_v1_advertisement(advert: BLEAdvertisement):
        if len(advert) != 31:
            return None

        manu_data = advert.manufacturer_data(ARCH_MANUFACTURER)

        _length, _datatype, _manu_id, device_uuid, flags = unpack("<BBHLH", manu_data)

        # Flags for version 1 are:
        #   bit 0: whether we have pending data
        #   bit 1: whether we are in a low voltage state
        #   bit 2: whether another user is connected
        #   bit 3: whether we support robust reports
        #   bit 4: whether we allow fast writes
        info = {'connection_string': advert.sender,
                'uuid': device_uuid,
                'pending_data': bool(flags & (1 << 0)),
                'low_voltage': bool(flags & (1 << 1)),
                'user_connected': bool(flags & (1 << 2)),
                'signal_strength': advert.rssi,
                'advertising_version': 1}

        payload = {'stream': None}

        if advert.scan_data:
            _length, _datatype, _manu_id, voltage, stream, reading, reading_time, curr_time = unpack("<BBHHHLLL11x", advert.scan_data)
            info['voltage'] = voltage / 256.0
            info['current_time'] = curr_time
            info['last_seen'] = datetime.datetime.now()

            payload = {
                'stream': stream,
                'value': reading,
                'timestamp': reading_time
            }

        return info, payload
