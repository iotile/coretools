from bable_interface import Characteristic, Service
import uuid

# Company ID
ArchManuID = 0x03C0

# GATT table
BLEService = Service(uuid='1800', handle=0x0001, group_end_handle=0x0005)
NameChar = Characteristic(
    uuid='2a00',
    handle=0x0002, value_handle=0x0003, const_value=b'V_IOTile ',
    read=True)
AppearanceChar = Characteristic(
    uuid='2a01',
    handle=0x0004, value_handle=0x0005, const_value=b'\x80\x00',
    read=True
)

TileBusService = Service(uuid=uuid.UUID('00002000-3ff7-53ba-e611-132c0ff60f63'), handle=0x000B, group_end_handle=0xFFFF)
ReceiveHeaderChar = Characteristic(
    uuid=uuid.UUID('00002001-0000-1000-8000-00805f9b34fb'),
    handle=0x000C, value_handle=0x000D, config_handle=0x000E,
    notify=True
)
ReceivePayloadChar = Characteristic(
    uuid=uuid.UUID('00002002-0000-1000-8000-00805f9b34fb'),
    handle=0x000F, value_handle=0x0010, config_handle=0x0011,
    notify=True
)
SendHeaderChar = Characteristic(
    uuid=uuid.UUID('00002003-0000-1000-8000-00805f9b34fb'),
    handle=0x0012, value_handle=0x0013,
    write=True
)
SendPayloadChar = Characteristic(
    uuid=uuid.UUID('00002004-0000-1000-8000-00805f9b34fb'),
    handle=0x0014, value_handle=0x0015,
    write=True
)
StreamingChar = Characteristic(
    uuid=uuid.UUID('00002005-0000-1000-8000-00805f9b34fb'),
    handle=0x0016, value_handle=0x0017, config_handle=0x0018,
    notify=True
)
HighSpeedChar = Characteristic(
    uuid=uuid.UUID('00002006-0000-1000-8000-00805f9b34fb'),
    handle=0x0019, value_handle=0x001A,
    write=True
)
TracingChar = Characteristic(
    uuid=uuid.UUID('00002007-0000-1000-8000-00805f9b34fb'),
    handle=0x001B, value_handle=0x001C, config_handle=0x001D,
    notify=True
)
