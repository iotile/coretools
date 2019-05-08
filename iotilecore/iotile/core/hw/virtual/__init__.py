"""Tools and base classes for implementing full IOTile devices in software

An IOTile device is defined as something you can connect to with
HardwareManager and interact with via its rpc, streaming, tracing, script, and
debug interfaces.

Many IOTile devices are physical, with an embedded microcontroller running
code that responds to requests on one of the above interfaces.

However, since the connection between HardwareManager and the device is
entirely mediated by an `class`:AbstractDeviceAdapter`, there is no need for
the device to be a physical thing.  If you have a device adapter that routes
requests from HardwareManager to a software program such as a TCP or websockets
server then there is no need for physical hardware.

The classes and functions in this subpackage provide base implementations of
what is needed to create a software-only, "virtual", iotile device.

.. important::

    Just because virtual devices run in python, does not mean that you cannot
    interact with them from outside your computer.  If you attach a
    DeviceServer class to a virtual device then you can access that device via
    whatever mechanism the DeviceServer supports, which could be, for example,
    bluetooth, usb or wifi.

Put another way, this subpackage provides the resources to be able to
implement the *server* side of an IOTile device, referring to
``HardwareManager`` and most of CoreTools as the *client* side.

There are other server implementations such as one written in embedded C and
not included with CoreTools that serve an equivalent purpose.

The bottom line is that this package is designed to let you build iotile
devices in software without needing IOTile-specific hardware.


Developer Reference
===================

The base entrypoint for creating virtual devices is the class
:class:`BaseVirtualDevice`. It defines the bare minimum of what makes the
device iotile-compatible, including:

- supporting iotile interfaces that can be opened and closed
- having a way for clients to call an rpc
- having support for the device asynchronously push data to the user via its
  streaming and tracing interfaces.
- having a way for the device to receive a script from the client

.. note::

    There is no reference to "tiles" in the above description of a virtual device.
    Tiles, defined as subsystems of an iotile device with a unique address, are
    not a fundamental concept.  They just happen to be a useful way of organizing
    complex iotile devices into reuable modules.

All virtual devices that you create must inherit from :class:`BaseVirtualDevice`.
At a minimum you need to override a single function:

- :meth:`BaseVirtualDevice.call_rpc`: This is the method that will be called
  when a client wants to execute an RPC on your device.  It must execute the
  RPC and return the result or raise an exception.  If the RPC is implemented
  as a coroutine, it may return a coroutine or awaitable object containing the
  result / exception.

.. warning::

    Most developers will not want to inherit directly from
    :class:`BaseVirtualDevice`, because it doesn't provide convenience
    functionality that you likely want to use.  For that reason there are two
    premade subclasses: :class:`SimpleVirtualDevice` and
    :class:`StandardVirtualDevice`.

    ``SimpleVirtualDevice`` does not have support for tiles, it just allows
    you register RPCs with a fixed address and rpc_id on the device itself.
    It is useful for very simple things where you want a device that
    implements very few RPCs.

    ``StandardVirtualDevice`` requires that you create :class:`VirtualTile`
    clases that contain all of your RPC definitions and it allows you to load
    those tiles into a given address in the virtual device and then RPCs are
    delegated to the tiles.

    Most developers will want to inherit from :class:`StandardVirtualDevice`.


Virtual Device Lifecycle
------------------------

All virtual devices are run inside of a :class:`VirtualDeviceAdapter`, even
when they are served externally using a DeviceServer.  The DeviceServer
interacts with the VirtualDeviceAdapter, which in turn interacts with the
virtual device.

The lifecycle of a virtual device, then is entirely defined by the
VirtualDeviceAdapter that owns it.  In general the flow is as follows:

- The virtual device instance is created.  At this point it is not running,
  cannot respond to RPCs and no background work should be started.

- ``start(channel)`` is called on the virtual device.  This is equivalent to the
  virtual device "turning on".  It should start any background work that
  it needs to do and prepare to receive RPCs.  The ``channel`` paramater passed
  from ``VirtualDeviceAdapter`` to virtual device is an instance of
  :class:`VirtualAdapterAsyncChannel`, which has public methods that the device
  can call at any time to asynchronously push data to the user through its
  streaming and tracing interfaces.

- ``stop()`` is called when the virtual device should be stopped.  It is
  equivalent to powering down the virtual device.  All background work should
  be synchronously stopped and no more RPCs will be dispatched to the device.
  Any previously connected clients will have already been disconnected.

"""

from .virtualtile import VirtualTile
from .virtualtile_base import BaseVirtualTile
from .virtualdevice_base import BaseVirtualDevice, AbstractAsyncDeviceChannel
from .virtualdevice_standard import StandardVirtualDevice
from .virtualdevice_simple import SimpleVirtualDevice

from .common_types import (rpc, tile_rpc, unpack_rpc_payload, pack_rpc_payload,
                           pack_rpc_response, unpack_rpc_response, RPCDispatcher,
                           RPCDeclaration)

__all__ = ['BaseVirtualTile', 'VirtualTile', 'BaseVirtualDevice',
           'AbstractAsyncDeviceChannel', 'StandardVirtualDevice',
           'RPCDeclaration', 'SimpleVirtualDevice', 'tile_rpc', 'rpc',
           'unpack_rpc_payload', 'pack_rpc_payload', 'pack_rpc_response',
           'unpack_rpc_response']
