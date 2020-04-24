"""Common classes and manager objects often needed in BLE implementations.

The classes inside this subpackage generally implement subsystems for tracking
scan requester or metadata associated with active connections in a way that is
not specific to IOTile devices but generally required for creating robust BLE
Central or Peripheral implementations.
"""

from .scan_manager import BLEScanManager

__all__ = ['BLEScanManager']
