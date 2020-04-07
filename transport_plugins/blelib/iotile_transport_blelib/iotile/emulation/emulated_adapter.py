"""An IOTile DeviceAdapter that reports emulated bluetooth devices.

This adapter is designed to allow real-world testing of code that needs to
handle large numbers of bluetooth devices.  It is built on top of VirtualAdapter
so that any virtual device implementation can be plugged in but it wraps each
virtual device in a bluetooth protocol shell so that rpcs, connections, broadcasts
and advertisements happen in the same way as real bluetooth devices.

This allows for injecting bluetooth errors such as missed advertisement packets,
early disconnects and connection timeouts and making sure higher level code is
robust to those changes.
"""

from typing import Optional
from iotile.core.utilities.async_tools import SharedLoop
from iotile.core.hw.virtual import load_virtual_device
from ..generic_adapter import GenericBLEDeviceAdapter
from .emulated_central import EmulatedBLECentral
from .emulated_device import EmulatedBLEDevice

class EmulatedBLEDeviceAdapter(GenericBLEDeviceAdapter):
    def __init__(self, port, *, loop=SharedLoop):
        devs, _settings = _parse_port_string(port, loop)
        central = EmulatedBLECentral(devs, loop=loop)

        super(EmulatedBLEDeviceAdapter, self).__init__(central, loop=loop)


def _parse_port_string(port: Optional[str], loop):
    if port is None:
        return [], {}

    devs = []
    settings = {}

    for part in port.split(';'):
        if part.startswith('$'):
            #TODO: Process key=value settings
            continue

        name, _sep, config = part.partition('@')
        loaded_dev, _config_dict = load_virtual_device(name, config, loop)

        mac = _build_mac_address(loaded_dev.iotile_id)
        ble_dev = EmulatedBLEDevice(mac, loaded_dev)
        devs.append(ble_dev)

    return devs, settings


def _build_mac_address(iotile_id: int):
    return "00:00:00:00:00:00"
