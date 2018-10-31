"""Base classes for virtual IOTile devices designed to emulate physical IOTile Devices.

Classes that derive from EmulatedDevice and EmulatedTile have additional funtionality
for saving and loading their state to provide for easy creation of testing scenarios.

For example, you may have an IOTile Device that serves as a shock and vibration data
logger.  In reality it would take time to load it up with real captured shocks and
vibrations in order to test that we could properly create software that read those
waveforms.  With an EmulatedDevice, you can just load in a `has 100 waveforms`
scenario and use that as part of automated integration test cases.

EmulatedDevice vs VirtualIOTileDevice
=====================================

In general a VirtualIOTileDevice is not designed to emulate a physical device.
A virtual device is a full-fledged IOTile device that just happens to be
running on a normal computer rather than on low-power embedded hardware.

An EmulatedDevice or EmulatedTile is a virtual IOTile device or tile whose
sole purpose in life is to be an emulator for some particular physical tile or
device.

For example, we could have a POD-1M emulator, that would be an EmulatedDevice,
whereas the network configuration device running on an Access Point is just a
normal virtual device.

The idea is that EmulatedTile classes can live with each tile firmware and
EmulatedDevice classes with each production device. The Emulated{Tile,Device}
stays in sync with the features of the physical {tile,device} and provides a
good way to do integration tests of other software components that need to
interact with that physical device.
"""

from .emulated_device import EmulatedDevice
from .emulated_tile import EmulatedTile
from .simple_state import SerializableState

__all__ = ['EmulatedDevice', 'EmulatedTile', 'SerializableState']
