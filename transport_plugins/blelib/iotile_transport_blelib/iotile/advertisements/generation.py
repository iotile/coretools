"""Internal routines for generating and validating iotile ble advertisements."""

from typing import Optional, Union, Tuple
import datetime
import struct
from typedargs.exceptions import ArgumentError
from iotile.core.hw.reports import IOTileReading
from ..constants import TileBusService, ARCH_MANUFACTURER, IOTILE_SERVICE_UUID_16
from ...defines import AdElementType, GAPAdFlags, AdvertisementType
from ...interface import BLEAdvertisement
from .utilities import timestamp_to_integer, generate_rotated_key, generate_nonce, encrypt_v2_packet

class AdvertisementOptions:  #pylint:disable=too-few-public-methods;This is a data class
    """Options to control how an advertisement is generated.

    This class can be used for v1 and v2 advertisements.  Not all options are
    supported on both advertisement types.
    """

    NO_ENCRYPTION = 0
    NULL_KEY = 1
    USER_KEY = 2
    DEVICE_KEY = 3

    _NULL_KEY = bytes(16)

    _MAX_VOLTAGE_V1 = 0xFFFF
    _MAX_BATTERY_LEVEL_V2 = 0xFF

    _MAX_BROADCAST_ID = 7
    _MAX_UPDATE_COUNT = 31
    _MAX_ENCRYPTION_TYPE = 7

    _KEY_FLAG_MAP = {
        'none': NO_ENCRYPTION,
        'null': NULL_KEY,
        'user': USER_KEY,
        'device': DEVICE_KEY
    }

    # Shared settings between v1 and v2 advertisements
    low_voltage = False  # type: bool
    user_connected = False  # type: bool
    has_data = False  # type: bool

    # V1 only settings
    voltage = 0xFFFF  # type: int
    robust_reports = True  # type: bool
    fast_writes = True     # type: bool

    # V2 only settings
    battery_level = 0xFF
    encryption_type = 0  # type: int
    reboot_key = None  # type: Optional[bytes]
    reboot_count = 0  # type: int
    broadcast_id = 0  # type: int
    update_count = 0  # type: int
    broadcast_toggle = False  # type: bool

    def validate_for_v1(self):
        """Verify the advertisement options are allowed for a v1 advertisement packet."""

        if self.voltage < 0 or self.voltage > self._MAX_VOLTAGE_V1:
            raise ArgumentError("Out of range voltage for v1 advertisement: %s" % self.voltage)

    def validate_for_v2(self):
        """Verify the advertisement options are allowed for a v2 advertisement packet."""

        if self.battery_level < 0 or self.battery_level > self._MAX_BATTERY_LEVEL_V2:
            raise ArgumentError("Out of range battery_level for v2 advertisement: %s" % self.battery_level)

        self._validate_encryption_settings()

    def is_encrypted(self) -> bool:
        """Check if this packet should be encrypted."""

        return self.encryption_type != self.NO_ENCRYPTION

    def configure_encryption(self, type_: str = "none", reboot_key: Optional[bytes] = None,
                             reboot_count: Optional[int] = None):
        """Convenience routine to specify encryption parameters correctly.

        This method raises an exception if there is an invalid combination of parameters
        given.

        Args:
            type_: The type of encryption to perform.  Currently this just configures the
                source key material used.  Options are the literal strings, "none", "null", "device",
                or "user" to specify no encryption, user key based encryption or device key
                based encryption.  The interpretation of the words user and device are
                unspecified and correspond to internal firmware settings with the same name.
            reboot_key: If encryption is to be performed, a 128-bit AES compatible key needs to
                be specified.  The key given here should be a long-lived key that is calculated
                from the root key specified in ``type_`` after every reboot.  Internally, a
                transient rotating key will be derived from this key based on the ``current_time``
                field in the advertising data.
                If ``null`` is specified as the ``type_`` of encryption, then the reboot key is
                ignored and the global ``null`` key is used instead.
            reboot_count: The monotonically increasing counter of how many times the device has
                rebooted.  This information is required to match what was used to generate
                the ``reboot_key`` so that receivers of the advertisement are able to calculate
                their own reboot key to decrypt the device's traffic.
        """

        int_type = self._KEY_FLAG_MAP.get(type_)
        if int_type is None:
            raise ArgumentError("Unknown encryption type specified: %s" % type_)

        self.encryption_type = int_type
        if reboot_count is not None:
            self.reboot_count = reboot_count

        if type_ == 'none':
            self.reboot_key = None
        elif type_ == 'null':
            self.reboot_key = self._NULL_KEY
        else:
            self.reboot_key = reboot_key

        self._validate_encryption_settings()

    def _validate_encryption_settings(self):
        if self.encryption_type == 0:
            return

        if self.encryption_type < 0 or self.encryption_type > self._MAX_ENCRYPTION_TYPE:
            raise ArgumentError("Out of range encryption_type for v2 advertisement: %s" % self.encryption_type)

        if self.encryption_type == self.NULL_KEY and self.reboot_key != self._NULL_KEY:
            raise ArgumentError("Invalid (non-null) encryption key specified for null encryption mode")

        if not isinstance(self.reboot_key, bytes) and len(self.reboot_key) != 16:
            raise ArgumentError("Invalid reboot key specified, expected a length 16 bytes object, was: %r"
                                % self.reboot_key)


_DEFAULT_OPTIONS = AdvertisementOptions()


def generate_v1_advertisement(iotile_id: int, *, broadcast: Optional[IOTileReading] = None,
                              options: Optional[AdvertisementOptions] = None,
                              current_time: Union[int, datetime.datetime] = 0) -> Tuple[bytes, bytes]:
    """Generate a version 1 bluetooth advertisement.

    This function should be useful primarily for testing ble central
    implementations for proper handling of V1 advertisements.  It can also be
    considered a reference for what the parts of a V1 advertisement mean.

    This is a low level function.  It returns the raw byte contents of the
    advertising packet as well as the scan response packet.  Unless
    active-scanning is enabled, the scan response packet would not actually be
    transmitted by a real iotile device.

    Args:
        iotile_id: The UUID of the IOTIle device.  This is encoded as a 32-bit unsigned
            integer.
        broadcast: If a broadcast reading should be included in the scan response
            data, it can be passed here.  The default behavior is to include no broadcast
            reading.
        options: Any flags or additional information that should be included in the
            advertisement.
        current_time: The raw device clock.  You can either specify an integer uptime, which
            is interpreted as the number of seconds since the last reboot, or you can specify
            a UTC datetime, which is converted to an internal integer representation and sent.

    Returns:
        The 31-byte advertisement packet and the 31-byte scan response packet.
    """

    if options is None:
        options = _DEFAULT_OPTIONS

    options.validate_for_v1()

    flags = ((int(options.has_data) << 0) | (int(options.low_voltage) << 1)) | (int(options.user_connected) << 2)
    ble_flags = struct.pack("<BBB", 2, AdElementType.FLAGS,
                            GAPAdFlags.LE_GENERAL_DISC_MODE | GAPAdFlags.BR_EDR_NOT_SUPPORTED)
    uuid_list = struct.pack("<BB16s", 17, AdElementType.INCOMPLETE_UUID_128_LIST,
                            TileBusService.UUID.bytes_le)
    manu_data = struct.pack("<BBHLH", 9, AdElementType.MANUFACTURER_DATA,
                            ARCH_MANUFACTURER, iotile_id, flags)
    advertisement = ble_flags + uuid_list + manu_data

    if broadcast is None:
        stream = 0xFFFF
        value = 0
        timestamp = 0
    else:
        stream = broadcast.stream
        value = broadcast.value
        timestamp = broadcast.raw_time

    current_time = timestamp_to_integer(current_time)

    scan_data = struct.pack("<BBHHHLLL3x", 21, AdElementType.MANUFACTURER_DATA, ARCH_MANUFACTURER,
                            options.voltage, stream, value, timestamp, current_time)
    name = struct.pack("<BB6s", 7, AdElementType.COMPLETE_LOCAL_NAME, b"IOTile")
    scan_response = scan_data + name

    return advertisement, scan_response


def generate_v2_advertisement(iotile_id: int, *, broadcast: Optional[IOTileReading] = None,
                              options: Optional[AdvertisementOptions] = None,
                              current_time: Union[int, datetime.datetime] = 0) -> bytes:
    """Generate a v2 advertisement packet.

    V2 advertisements are modern single packet bluetooth low energy
    advertisements that support including the broadcast reading inside the
    advertisement itself (rather than as a scan response) and support
    encrypting the broadcast data and authenticating the packet source.

    Args:
        iotile_id: The UUID of the IOTIle device.  This is encoded as a 32-bit unsigned
            integer.
        broadcast: If a broadcast reading should be included in the scan response
            data, it can be passed here.  The default behavior is to include no broadcast
            reading.
        options: Any flags or additional information that should be included in the
            advertisement.
        current_time: The raw device clock.  You can either specify an integer uptime, which
            is interpreted as the number of seconds since the last reboot, or you can specify
            a UTC datetime, which is converted to an internal integer representation and sent.

    """

    if options is None:
        options = _DEFAULT_OPTIONS

    options.validate_for_v2()

    ble_flags = struct.pack("<BBB", 2, AdElementType.FLAGS,
                            GAPAdFlags.LE_GENERAL_DISC_MODE | GAPAdFlags.BR_EDR_NOT_SUPPORTED)

    flags = ((int(options.has_data) << 0) | (int(options.low_voltage) << 1)) | (int(options.user_connected) << 2)
    broadcast_info = (options.update_count & 0b11111) | ((options.broadcast_id & 0b111) << 5)
    current_time = timestamp_to_integer(current_time)

    if broadcast is None:
        packed_stream = 0xFFFF
        value = 0
    else:
        packed_stream = broadcast.stream | (int(options.broadcast_toggle) << 15)
        value = broadcast.value

    service_data = struct.pack("<BBHLHBBLBBHLL", 27, AdElementType.SERVICE_DATA_UUID_16,
                               IOTILE_SERVICE_UUID_16, iotile_id, options.reboot_count & 0xFFFF,
                               options.reboot_count >> 16, flags, current_time,
                               options.battery_level, broadcast_info, packed_stream, value, 0)

    advertisement = ble_flags + service_data
    if options.is_encrypted():
        assert options.reboot_key is not None
        ephemeral_key = generate_rotated_key(options.reboot_key, current_time)
        nonce = generate_nonce(iotile_id, current_time, options.reboot_count, broadcast_info)
        advertisement = encrypt_v2_packet(advertisement, ephemeral_key, nonce)

    return advertisement


def generate_advertisement(iotile_id: int, version: str, mac: str, rssi: float, *,
                           broadcast: Optional[IOTileReading] = None,
                           options: Optional[AdvertisementOptions] = None,
                           current_time: Union[int, datetime.datetime] = 0) -> BLEAdvertisement:
    """Convenience routine to generate a v1 or v2 advertisement programmatically.

    There are direct functions for generating the raw advertisement bytes for
    a v1 or v2 advertisement packet but those force the user to wrap those raw
    bytes inside of a BLEAdvertisement object themselves.  This convenience
    routines handles everything in a single call, including setting the right
    BLE PDU type (connectable or not) based on whether or not there is a
    current user connected to the device and the advertising format.

    Returns:
        The constructed BLEAdvertisement.
    """

    if version not in ('v1', 'v2'):
        raise ArgumentError("Unsupport advertisement version: %s, must be v1 or v2" % version)

    if options is None:
        options = _DEFAULT_OPTIONS

    scan_response = None  #type: Optional[bytes]

    if version == 'v1':
        advert, scan_response = generate_v1_advertisement(iotile_id, broadcast=broadcast,
                                                          options=options, current_time=current_time)
        if options.user_connected:
            kind = AdvertisementType.SCANNABLE
        else:
            kind = AdvertisementType.CONNECTABLE
    else:
        advert = generate_v2_advertisement(iotile_id, broadcast=broadcast,
                                           options=options, current_time=current_time)

        if options.user_connected:
            kind = AdvertisementType.NONCONNECTABLE
        else:
            kind = AdvertisementType.CONNECTABLE

    return BLEAdvertisement(mac, kind, rssi, advert, scan_response)
