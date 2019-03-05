"""A generic RPC-level emulator for any IOTile device.

This package provides a framework that lets you emulate any IOTile device.
It includes:

- A generic emulation system based on the EmulationLoop class.  This is the
  basis for the emulation and allows running coroutines simulating tiles
  inside a single event loop and communication with those coroutines using
  RPC.
- A VirtualIOTileDevice subclass EmulatedDevice that includes the
  EmulationLoop and wraps it in an interface that can be handled to any
  VirtualInterface and served like a normal virtual device.  This means that
  you can make an emulated device available over any protocol that has a
  virtual interface such as bluetooth, websockets or MQTT.
- A reference implemention of the IOTile bus controller in Python, in the
  ReferenceController class.  This allows for the emulation of physical IOTile
  devices by just writing small classes that emulate the behavior of the
  peripheral tiles.  The ReferenceDevice class is the correct base class for
  these endeavors.
- A device adapter that allows you to directly run an EmulatedDevice inside
  of the iotile tool for testing and demos.
"""

from .virtual import EmulatedDevice, EmulatedTile, EmulatedPeripheralTile
from . import constants
from .common import RPCRuntimeError

__all__ = ['EmulatedTile', 'EmulatedDevice', 'EmulatedPeripheralTile', 'constants', 'RPCRuntimeError']
