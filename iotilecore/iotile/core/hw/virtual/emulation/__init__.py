"""Base classes for virtual IOTile devices designed to emulate physical IOTile Devices.

Classes that derive from EmulatedDevice and EmulatedTile have additional funtionality
for saving and loading their state to provide for easy creation of testing scenarios.

For example, you may have an IOTile Device that serves as a shock and vibration data
logger.  In reality it would take time to load it up with real captured shocks and
vibrations in order to test that we could properly create software that read those
waveforms.  With an EmulatedDevice, you can just load in a `has 100 waveforms`
scenario and use that as part of automated integration test cases.
"""

from .emulated_device import EmulatedDevice
from .emulated_tile import EmulatedTile

__all__ = ['EmulatedDevice', 'EmulatedTile']
