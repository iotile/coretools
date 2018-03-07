"""All currently support record types for remote update scripts."""

from .reflash_tile import ReflashTileRecord
from .unknown import UnknownRecord
from .send_rpc import SendRPCRecord, SendErrorCheckingRPCRecord
from .reflash_controller import ReflashControllerRecord
from .reset_device import ResetDeviceRecord
from ..record import UpdateRecord

# Register all of our record types to be decodable (we don't register UnknownRecord)
UpdateRecord.RegisterRecordType(ReflashTileRecord)
UpdateRecord.RegisterRecordType(SendRPCRecord)
UpdateRecord.RegisterRecordType(SendErrorCheckingRPCRecord)
UpdateRecord.RegisterRecordType(ReflashControllerRecord)
UpdateRecord.RegisterRecordType(ResetDeviceRecord)

__all__ = ['ReflashTileRecord', 'UnknownRecord', 'SendRPCRecord', 'SendErrorCheckingRPCRecord', 'ReflashControllerRecord']
