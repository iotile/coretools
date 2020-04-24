"""All IOTile specific definitions go in here.

This subpackage isolates anything IOTile specific, such as Gatt Service and
Charactistic UUIDs so that the rest of the `blelib` package can be generic to
bluetooth support.
"""

from .constants import TileBusService, ARCH_MANUFACTURER, IOTILE_SERVICE_UUID
from .generic_adapter import GenericBLEDeviceAdapter

__all__ = ['GenericBLEDeviceAdapter']
