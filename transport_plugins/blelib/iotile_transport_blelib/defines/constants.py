"""Constant enumerations and values used in BLE communication."""

from enum import IntEnum
from .compact_uuid import expand_uuid

class AttributeType:
    """Defined types of Gatt attributes."""

    CHAR_DECLARATION = expand_uuid(uint16=0x2803)
    CLIENT_CONFIG = expand_uuid(uint16=0x2902)
    PRIMARY_SERVICE = expand_uuid(uint16=0x2800)


class AdvertisementType:
    """Defined types of BLE advertisement packets."""

    CONNECTABLE = 0x00
    NONCONNECTABLE = 0x02
    SCAN_RESPONSE = 0x04
    SCANNABLE = 0x06


class AdElementType(IntEnum):
    """Types of data elements that can be found in an advertisement.

    The complete list of such ad elements can be found at:
    https://www.bluetooth.com/specifications/assigned-numbers/generic-access-profile/
    """

    FLAGS = 1
    INCOMPLETE_UUID_16_LIST = 2
    COMPLETE_UUID_16_LIST = 3
    INCOMPLETE_UUID_32_LIST = 4
    COMPLETE_UUID_32_LIST = 5
    INCOMPLETE_UUID_128_LIST = 6
    COMPLETE_UUID_128_LIST = 7
    SHORTENED_LOCAL_NAME = 8
    COMPLETE_LOCAL_NAME = 9
    TX_POWER_LEVEL = 0xA

    # Numerical gap, these are not assigned

    DEVICE_CLASS = 0xD
    SIMPLE_PAIRING_HASH = 0xE
    SIMPLE_PAIRING_RANDOMIZER = 0xF

    SECURITY_TK_VALUE = 0x10
    SECURITY_OOB_FLAGS = 0x11
    SLAVE_CONN_INTERVAL_RANGE = 0x12

    SOLICITATION_UUID_16_LIST = 0x14

    # TODO: add in the other element types

    SERVICE_DATA_UUID_16 = 0x16

    SERVICE_DATA_UUID_32 = 0x20
    SERVICE_DATA_UUID_128 = 0x21

    MANUFACTURER_DATA = 0xFF


class GAPAdFlags(IntEnum):
    """BLE well known flags indicating device capabilities."""

    LE_LIMITED_DISC_MODE = 0x01
    LE_GENERAL_DISC_MODE = 0x02
    BR_EDR_NOT_SUPPORTED = 0x04
    LE_BR_EDR_CONTROLLER = 0x08
    LE_BR_EDR_HOST = 0x10
