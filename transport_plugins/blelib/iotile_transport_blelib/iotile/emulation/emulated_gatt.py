"""Emulated Gatt database."""

import uuid
import struct
from ...interface.gatt import GattTable, GattService, GattAttribute, GattCharacteristic, CharacteristicProperties
from ...interface.errors import MissingHandleError
from ...defines import compact_uuid, AttributeType

class _AttributeGroup:
    def __init__(self, uuid: uuid.UUID, start_handle: int, end_handle: int):
        self.group_uuid = uuid
        self.start_handle = start_handle
        self.end_handle = end_handle


class EmulatedGattTable(GattTable):
    """Internal support class for creating a valid GATT table.

    This class ensures that GATT services and characteristics are laid out in
    a contiguous handle space as would be the case in an actual bluetooth
    device.
    """

    def __init__(self):
        super(EmulatedGattTable, self).__init__()

        self.raw_handles = []
        self._handle_char_map = {}
        self.groups = []

    def lookup_handle(self, handle: int):
        if handle not in self._handle_char_map:
            raise MissingHandleError(handle)

        handle_index = handle - 1

        return self.raw_handles[handle_index], self._handle_char_map[handle]

    def iter_handles(self, start: int, end: int):
        """Iterate over all handles between start and end, inclusive."""

        start -= 1
        for i in range(start, end):
            yield self.raw_handles[i]

    def update_handles(self):
        """Recalculate the handle number of all attributes."""

        self.raw_handles = []
        self.groups = []
        self._handle_char_map = {}

        for service in self.services:
            start = len(self.raw_handles) + 1
            end = start + _count_attributes(service.characteristics) - 1

            service_att = GattAttribute(start, compact_uuid(service.uuid), AttributeType.PRIMARY_SERVICE)
            self.raw_handles.append(service_att)

            for char in service.characteristics.values():
                char_start = len(self.raw_handles) + 1
                attributes = _create_char_attributes(char_start, char)
                self.raw_handles.extend(attributes)

                for att in attributes:
                    self._handle_char_map[att.handle] = char

            group = _AttributeGroup(service.uuid, start, end)
            self.groups.append(group)

    def quick_add(self, service_uuid: uuid.UUID, char_uuid: uuid.UUID, **kwargs):
        """Quickly add a new characteristic to this emulated gatt table.

        If the given service does not exist, it is added first.  After making
        changes to the gatt table, you must call ``update_handles`` to assign
        valid handle numbers to all of the handles in the table.
        """

        try:
            service = self.find_service(service_uuid)
        except KeyError:
            service = GattService(service_uuid)
            self.services.append(service)

        props = CharacteristicProperties(**kwargs)

        config = None
        if props.notify or props.indicate:
            config = GattAttribute(0, bytes([0, 0]), AttributeType.CLIENT_CONFIG)

        value = GattAttribute(0, b'', char_uuid)
        char = GattCharacteristic(char_uuid, props, value, config)

        service.characteristics[char_uuid] = char



def _count_attributes(chars):
    count = 0

    for char in chars.values():
        if char.client_config is not None:
            count += 3
        else:
            count += 2

    return count


def _create_char_attributes(start_handle, char):
    attributes = []

    uuid_bytes = compact_uuid(char.uuid)

    declaration_value = struct.pack("<BH%ds" % len(uuid_bytes),
                                    char.properties.int_value, start_handle + 1, uuid_bytes)
    declaration = GattAttribute(start_handle, declaration_value, AttributeType.CHAR_DECLARATION)

    attributes.append(declaration)

    value = GattAttribute(start_handle + 1, b'', char.uuid)
    attributes.append(value)

    config = None
    if char.properties.notify or char.properties.indicate:
        config = GattAttribute(start_handle + 2, bytes([0, 0]), AttributeType.CLIENT_CONFIG)
        attributes.append(config)

    # Update the GATT characteristic itself to be consistent with the new handle numbering
    char.value = value
    char.client_config = config

    return attributes
