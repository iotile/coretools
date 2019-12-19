import uuid
from ..defines import expand_uuid

class TileBusService:
    """Definition of the TileBus v1 Gatt Service.

    These enumerations define the UUIDs of all characteristics that
    are currently in use for TileBus communication over BLE.
    """

    UUID = uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')

    # Characteristics in the service
    SEND_HEADER = uuid.UUID('fb349b5f-8000-0080-0010-000000000320')
    SEND_PAYLOAD = uuid.UUID('fb349b5f-8000-0080-0010-000000000420')
    RECEIVE_HEADER = uuid.UUID('fb349b5f-8000-0080-0010-000000000120')
    RECEIVE_PAYLOAD = uuid.UUID('fb349b5f-8000-0080-0010-000000000220')
    STREAMING = uuid.UUID('fb349b5f-8000-0080-0010-000000000520')
    HIGHSPEED = uuid.UUID('fb349b5f-8000-0080-0010-000000000620')
    TRACING = uuid.UUID('fb349b5f-8000-0080-0010-000000000720')


ARCH_MANUFACTURER = 0x03C0
IOTILE_SERVICE_UUID_16 = 0xFDDD
IOTILE_SERVICE_UUID = expand_uuid(uint16=IOTILE_SERVICE_UUID_16)
