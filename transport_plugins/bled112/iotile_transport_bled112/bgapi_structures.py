import struct
import uuid
from iotile.core.utilities.packed import unpack
from collections import namedtuple

CharacteristicProperties = namedtuple("CharacteristicProperties", ["broadcast", "read", "write_no_response", "write", "notify", "indicate", "write_authenticated", "extended"])

def process_uuid(guiddata):
    guiddata = bytearray(guiddata)

    if len(guiddata) == 3 or len(guiddata) == 5 or len(guiddata) == 17:
        guiddata = guiddata[1:]

    if (not len(guiddata) == 2) and (not len(guiddata) == 16) and (not len(guiddata) == 4):
        raise ValueError("Invalid guid length, is not 2, 4 or 16. Data=%s" % (str(guiddata)))

    #Byte order is LSB first for the entire guid
    if len(guiddata) != 16:
        base_guid = uuid.UUID(hex="{FB349B5F8000-0080-0010-0000-00000000}").bytes_le
        base_guid = base_guid[:-len(guiddata)] + str(guiddata)

        return uuid.UUID(bytes_le=base_guid)

    return uuid.UUID(bytes_le=str(guiddata))

def process_gatt_service(services, event):
    """Process a BGAPI event containing a GATT service description and add it to a dictionary

    Args:
        services (dict): A dictionary of discovered services that is updated with this event
        event (BGAPIPacket): An event containing a GATT service
    
    """

    length = len(event.payload) - 5

    handle, start, end, uuid = unpack('<BHH%ds' % length, event.payload)

    uuid = process_uuid(uuid)
    services[uuid] = {'uuid_raw': uuid, 'start_handle': start, 'end_handle': end}

def process_read_handle(event):
    length = len(event.payload) - 5
    conn, att_handle, att_type, act_length, value = unpack("<BHBB%ds" % length, event.payload)

    assert act_length == length

    return att_type, bytearray(value)

def process_attribute(attributes, event):
    length = len(event.payload) - 3
    handle, chrhandle, uuid = unpack("<BH%ds" % length, event.payload)
    uuid = process_uuid(uuid)
    
    attributes[chrhandle] = {'uuid': uuid}

def parse_characteristic_declaration(value):
    length = len(value)

    if length == 5:
        uuid_len = 2
    elif length == 19:
        uuid_len = 16
    else:
        raise ValueError("Value has improper length for ble characteristic definition, length was %d" % len(value))

    propval, handle, uuid = unpack("<BH%ds" % uuid_len, value)


    #Process the properties
    properties = CharacteristicProperties(bool(propval & 0x1), bool(propval & 0x2), bool(propval & 0x4), bool(propval & 0x8), 
                                          bool(propval & 0x10), bool(propval & 0x20), bool(propval & 0x40), bool(propval & 0x80))

    uuid = process_uuid(uuid)
    char = {}
    char['uuid'] = uuid
    char['properties'] = properties
    char['handle'] = handle

    return char

def handle_to_uuid(handle, services):
    """Find the corresponding UUID for an attribute handle
    """

    for service in services.itervalues():
        for char_uuid, char_def in service['characteristics'].iteritems():
            if char_def['handle'] == handle:
                return char_uuid

    raise ValueError("Handle not found in GATT table")


def process_notification(event):
    length = len(event.payload) - 5
    conn, att_handle, att_type, act_length, value = unpack("<BHBB%ds" % length, event.payload)

    assert act_length == length
    return att_handle, bytearray(value)
