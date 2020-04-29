"""Asycnio implementation of BLE adapter for bled112"""

from iotile.core.utilities.async_tools import SharedLoop
from iotile_transport_blelib.iotile import GenericBLEDeviceAdapter
from .async_central import BLED112Central

class BLED112Adapter(GenericBLEDeviceAdapter):
    """docstring for BLED112DeviceAdapter"""
    def __init__(self, port: str, *, loop=SharedLoop):
        #parse port and instanticate the device
        central = BLED112Central(port, loop=loop)

        super(BLED112Adapter, self).__init__(central=central, loop=loop)
