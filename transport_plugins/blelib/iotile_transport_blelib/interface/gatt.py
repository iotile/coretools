"""Common class definitions for GATT tables."""

from typing import List, Optional
from uuid import UUID
import struct
from .errors import UnsupportedOperationError


class CharacteristicProperties:
    """Representation of the properties of a GattCharacteristic.

    This convience class holds all of the permitted actions on a characteristic
    and also allows encoding them into their binary value.
    """

    broadcast = False
    read = False
    write_no_response = False
    write = False
    notify = False
    indicate = False
    write_authenticated = False
    extended = False

    def __init__(self, *, broadcast=False, read=False, write_no_response=False, write=False,
                 notify=False, indicate=False, write_authenticated=False, extended=False):
        self.broadcast = broadcast
        self.read = read
        self.write_no_response = write_no_response
        self.write = write
        self.notify = notify
        self.indicate = indicate
        self.write_authenticated = write_authenticated
        self.extended = extended

    @property
    def int_value(self):
        """The uint8 integer representing these permissions.

        This integer is encoded as specified in the bluetooth standard, mapping
        each permission to its designated bit.
        """

        value = 0
        value |= int(self.broadcast) << 0
        value |= int(self.read) << 1
        value |= int(self.write_no_response) << 2
        value |= int(self.write) << 3
        value |= int(self.notify) << 4
        value |= int(self.indicate) << 5
        value |= int(self.write_authenticated) << 6
        value |= int(self.extended) << 7

        return value


class GattAttribute:
    """Representation of a Gatt Attribute.

    Attributes are the atomic unit that is read or written inside of a
    GATT table.  They are all allocated a 16-bit handle identifier to
    permit direct access.  GattCharacteristics are made up of one or
    more attributes.

    Args:
        handle: The handle value that can be used to read or write this
            attribute.
        value: The current value of the attribute
        kind: The Bluetooth type of the attribute, such as client config
            descriptor, service declaration, etc.
    """

    def __init__(self, handle: int, value: bytes, kind: UUID):
        self.handle = handle
        self.raw_value = value
        self.type = kind

    @property
    def int_value(self):
        """The value of the attribute as a 16-bit little endian integer."""

        if len(self.raw_value) != 2:
            raise ValueError("Cannot convert attribute value to int because its the wrong size")

        return struct.unpack('<H', self.raw_value)[0]

    @int_value.setter
    def int_value(self, value):
        """Set the value of the attribute from a 16-bit little endian integer."""

        if len(self.raw_value) != 2:
            raise ValueError("Cannot wrtie integer value because attribute is the wrong size")

        self.raw_value = struct.pack("<H", value)


class GattCharacteristic:
    """Representation of a GATT characteristic.

    GATT characteristics are the core unit of a GATT database and are the
    named objects that can be read, written and subscribed to.

    Args:
        uuid: The UUID of the characteristic
        properties: The actions that are permitted on the characteristic
        value_att: The attribute holding the value of the characteristic
        config_att: If the characteristic supports subscriptions, the
            attribute holding the client configuration descriptor indicating
            if the client is subscribed.
    """

    def __init__(self, uuid: UUID, properties: CharacteristicProperties,
                 value_att: GattAttribute, config_att: GattAttribute = None):
        self.uuid = uuid
        self.properties = properties
        self.value = value_att
        self.client_config = config_att

    def can_subscribe(self, kind: str = "notify") -> bool:
        """Check whether subscriptions to this charactistic are possible.

        Args:
            kind: Either notify or indicate to check the corresponding type
                of subscription.

        Returns:
            Whether that kind of subscription is possible.

            Indications and notifications can be controlled independently.
        """

        if self.client_config is None:
            return False

        if kind == 'notify':
            return self.properties.notify

        if kind == 'indicate':
            return self.properties.indicate

        raise UnsupportedOperationError("Unknown subscription type: %s" % kind)

    def is_subscribed(self, kind: str = "notify") -> bool:
        """Check whether we are subscribed to this characteristic.

        Args:
            kind: Either notify or indicate to check the corresponding type
                of subscription.

        Returns:
            Whether we are currently subscribed.
        """

        if self.client_config is None:
            return False

        if kind == 'notify':
            return bool(self.client_config.int_value & (1 << 0))

        if kind == 'indicate':
            return bool(self.client_config.int_value & (1 << 1))

        raise UnsupportedOperationError("Unknown subscription type: %s" % kind)

    def modify_subscription(self, kind: str = "notify", enabled: bool = True) -> bool:
        """Update the client config to indicate a subscription.

        Args:
            kind: Either notify or indicate to check the corresponding type
                of subscription.
            enabled: Whether we want to enable or disable the subscription.

        Returns:
            Whether the subscription state changed.
        """

        if not self.can_subscribe(kind):
            raise UnsupportedOperationError("Characteristic does not support %s subscriptions" % kind)


        last_value = self.client_config.int_value  # type: ignore
        if kind == "notify":
            change = (1 << 0)
        else:
            change = (1 << 1)

        if enabled:
            value = last_value | change
        else:
            value = last_value & (~change)

        self.client_config.int_value = value  # type: ignore
        return value != last_value


class GattService:
    """Representation of a Bluetooth Service inside a GATT table."""

    def __init__(self, uuid: UUID, chars: Optional[List[GattCharacteristic]] = None):
        if chars is None:
            chars = []

        self.characteristics = {char.uuid: char for char in chars}
        self.uuid = uuid


class GattTable:
    """Representation of a remote GATT server's table of services/characteristics."""

    def __init__(self, services: Optional[List[GattService]] = None):
        if services is None:
            services = []

        self.services = services

    def find_char(self, char: UUID) -> GattCharacteristic:
        """Find a characteristics inside the peripheral's gatt table.

        This function looks up the corresponding characteristic based on the
        provided UUID.

        Args:
            char: The UUID to lookup

        Returns:
            The gatt characteristic

        Raises:
            KeyError: The desired characteristic was not found.
        """

        for service in self.services:
            if char in service.characteristics:
                return service.characteristics[char]

        raise KeyError("Character %s was not in GATT table" % char)

    def find_service(self, service_uuid: UUID) -> GattService:
        """Find a service inside the peripheral's gatt table.

        This function looks up the corresponding service based on the
        provided UUID.

        Args:
            char: The UUID to lookup

        Returns:
            The gatt service

        Raises:
            KeyError: The desired characteristic was not found.
        """
        for service in self.services:
            if service.uuid == service_uuid:
                return service

        raise KeyError("Service %s was not in GATT table" % service_uuid)
