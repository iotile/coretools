"""This module contains functions for parsing of advertising packets"""

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
    #   bit 3: Broadcast data is encrypted
    #   bit 4: Encryption key is device key
    #   bit 5: Encryption key is user key
    #   bit 6: broadcast data is time synchronized to avoid leaking
    #   information about when it changes
    is_pending_data = bool(flags & (1 << 0))
    is_low_voltage = bool(flags & (1 << 1))
    is_user_connected = bool(flags & (1 << 2))
    is_encrypted = bool(flags & (1 << 3))
    is_device_key = bool(flags & (1 << 4))
    is_user_key = bool(flags & (1 << 5))


    info = {'connection_string': advert.sender,
            'uuid': device_id,
            'pending_data': is_pending_data,
            'low_voltage': is_low_voltage,
            'user_connected': is_user_connected,
            'signal_strength': advert.rssi,
            'reboot_counter': reboots,
            'sequence': counter,
            'broadcast_toggle': broadcast_toggle, # FIX toggle is not decrypted at this point
            'timestamp': timestamp,
            'battery': battery / 32.0,
            'advertising_version':2}

    # key_type = AuthProvider.NoKey
    # if is_encrypted:
    #     if is_device_key:
    #         key_type = AuthProvider.DeviceKey
    #     elif is_user_key:
    #         key_type = AuthProvider.UserKey

    # if is_encrypted:
    #     if not _HAS_CRYPTO:
    #         return info, timestamp, None, None, None, None, None

    #     try:
    #         key = self._key_provider.get_rotated_key(key_type, device_id,
    #             reboot_counter=reboots,
    #             rotation_interval_power=EPHEMERAL_KEY_CYCLE_POWER,
    #             current_timestamp=timestamp)
    #     except NotFoundError:
    #         self._logger.warning("Key type {} is not found".format(key_type), exc_info=True)
    #         return info, timestamp, None, None, None, None, None

    #     nonce = generate_nonce(device_id, timestamp, reboot_low, reboot_high_packed, counter_packed)

    #     try:
    #         decrypted_data = decrypt_payload(key, data[7:], nonce)
    #     except ValueError:
    #         self._logger.warning("Advertisement packet is not verified", exc_info=True)
    #         return info, timestamp, None, None, None, None, None

    #     broadcast_stream_packed, broadcast_value = unpack("<HL", decrypted_data)
    #     broadcast_toggle = broadcast_stream_packed >> 15
    #     broadcast_stream = broadcast_stream_packed & ((1 << 15) - 1)

    # return info, timestamp, broadcast_stream, broadcast_value, \
    #     broadcast_toggle, counter, broadcast_multiplex

    return info


def parse_v1_advertisement(rssi: int, sender, advert: BLEAdvertisement):
    if len(advert) != 31:
        return None

    # Make sure the scan data comes back with an incomplete UUID list
    if advert[3] != 17 or advert[4] != 6:
        return None


    # Make sure the uuid is our tilebus UUID
    if advert.contains_service(TileBusService.UUID):
        # Now parse out the manufacturer specific data
        manu_data = advert[21:]

        _length, _datatype, _manu_id, device_uuid, flags = unpack("<BBHLH", manu_data)

        self._device_scan_counts.setdefault(device_uuid, {'v1': 0, 'v2': 0})['v1'] += 1

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
            return None

        return info
