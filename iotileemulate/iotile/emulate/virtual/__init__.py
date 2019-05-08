"""Base classes for virtual IOTile devices designed to emulate physical IOTile Devices.

Classes that derive from EmulatedDevice and EmulatedTile have additional
funtionality for saving and loading their state to provide for easy creation
of testing scenarios.

For example, you may have an IOTile Device that serves as a shock and
vibration data logger.  In reality it would take time to load it up with real
captured shocks and vibrations in order to test that we could properly create
software that read those waveforms.  With an EmulatedDevice, you can just load
in a `has 100 waveforms` scenario and use that as part of automated
integration test cases.


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


Lifecycle of an Emulated Device
===============================

Unlike normal virtual devices, which have no specific lifecycle imposed on
them, emulated devices are designed to act as standins for physical IOTile
devices that do need to follow a very specific initialization process.

The process is as follows:

- First the controller tile for the device boots and initializes itself.
- Each peripheral tile checks in with the controller tile and registers itself
    - this triggers the controller tile to stream any config variables that
      pertain to that peripheral tile.
    - once finished, the controller tile sends a start_application RPC to the
      peripheral tile and it begins operation.

In an EmulatedDevice class, this process happens when start() is called on the
device and when the controller is reset().  Each tile can also be reset
independently in order to trigger it to go through its initialization process
again (including registering and receiving new config variables).


Technical Details of Emulation
==============================

All emulation happens inside the EmulatedDevice subclass.  Nothing happens
on __init__ except for internal class initialization.  Emulation begins
when EmulatedDevice.start() is called and finishes when EmulatedDevice.stop()
is called.

Both start() and stop() are synchronous calls in that emulation is guaranteed
to be running when start() returns and guaranteed to be finished when stop()
returns.

Since start() and stop() are synchronous, they are not safe to call from
within the event loop that is used to run the simulation.

Conceptually start() is equivalent to powering on the emulated device and
stop() is equivalent to powering it off.

Emulation is performed inside of a BackgroundEventLoop using
:class:`EmulationLoop`. Each subsystem or tile inside the device that would
normally run in an RTOS task or on a separate processor instead runs as a
coroutine cooperatively scheduled with all other tasks inside the background
event loop.

There is a single background coroutine spawned by EmulatedDevice during the
start() method that is in charge of dispatching rpcs to each tile.  Any time a
tile wishes to communicate with another tile, it calls
``self.device.emulator.await_rpc()`` and this queues the rpc for completion on the
background rpc dispatcher task.  The caller can await that call in order to
yield until the rpc has finished.

There is a clear distinction between routines that are safe to call (by a
user) outside of the emulation loop an those that are not threadsafe and must
not be called outside of the emulation loop.  Some of the convenience methods
declared on ``EmulatedDevice`` can automatically detect what context they are
being called from to know whether they should block or return an awaitable.

This makes it safe to call methods like ``wait_idle``from both inside and outside
of the event loop.  However, some methods are marked to only be safe to call
from outside the event loop like ``EmulatedDevice.rpc()``.

Since all RPCs are guaranteed to only execute on a single thread, only one RPC
at a time can execute, as is the case in a physical IOTile device.

If you want to directly interact with an EmulatedDevice from a control script,
you can call the EmulatedDevice.rpc() method directly from your control
script.

Even though you are synchronously invoking the rpc() method, the rpc that you
specify will still be executed in the background rpc dispatch thread while
your thread blocks waiting for it to finish.

If you want to queue an RPC without blocking, you can use the deferred_rpc()
method, optionally passing a callback that will be invoked when the RPC
finishes.
"""

from .emulated_device import EmulatedDevice
from .peripheral_tile import EmulatedPeripheralTile
from .emulated_tile import EmulatedTile
from .simple_state import SerializableState

__all__ = ['EmulatedDevice', 'EmulatedTile', 'SerializableState', 'EmulatedPeripheralTile']
