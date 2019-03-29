"""Abstract interface for a class that serves access to IOTile devices.

This class can be thought of as a generic server that could be accessed
by an :class:`AbstractDeviceAdapter`.  This base class does not specify
anything about how the actual server works since that will vary widely.

The goal of declaring this base class is to standardize how such servers
are configured and started so that a generic "server container" such as
``iotile-gateway`` is capable of running any number of servers regardless
of their implementations.

It is, by design, entirely unspecified how a given device server chooses
to "make available" devices.  The only agreement needs to be between
a device server and the corresponding device adapter.

As a concrete example, consider the BLED112 DeviceAdapter.  This adapter acts
as a BLE central device, finding iotile devices by scanning for bluetooth low
energy (BLE) perihperal advertisements within range.  It sends rpcs by writing
to the iotile device's GATT server on specific characteristics.

A device server for BLED112 then would be a BLE peripheral that implements the
same GATT server as a phyiscal IOTile device and dispatches RPCs to its
internal adapter as they are received via writes to the agreed-upon
characterstics.

Given the highly normalized nature of IOTile interactions, they are easy to
proxy between communications modalities and form bridges connecting, e.g.
bluetooth and websockets or TCP and usb.
"""

import abc
from iotile.core.utilities import SharedLoop

class AbstractDeviceServer(abc.ABC):
    """A generic class that serves access to an IOTile compliant device.

    This class is the server side of a :class:`AbstractDeviceAdapter`.
    It is expected that there could be an AbstractDeviceServer for
    every AbstractDeviceAdapter implementation.

    In an analogy to HTTP, the DeviceAdapter is the HTTP client like
    Chrome or curl.  The DeviceServer is the HTTP server like nginx
    or apache.

    Note that there is very little specified here in terms of required
    interface except that arguments must be passed as an argument dictionary
    and the device server must take a single adapter argument that will
    be an AbstractDeviceAdapter.  The device server should use that device
    adapter to find, connect to and perform operations on devices.

    .. important:

        It is not the role of AbstractDeviceServer to ``start()`` or ``stop()``
        its device adapter.  It should assume that the adapter is already
        started by the time :meth:`start` is called and will be stopped
        after :meth:`stop` is called.

        This is important because there may well be multiple device servers
        attached to the same underlying device adapter.

    Args:
        adapter (AbstractDeviceAdapter): The device adapter that this
            device server should use to find and connect to devices.
        args (dict): Any arguments to the device adapter must be passed
            in as a dictionary so that they can be passed in a generic
            fashion.
        loop (BackgroundEventLoop): The event loop that the device server
            should use for blocking coroutine operations.  If not specified,
            this defaults to the global SharedLoop.
    """

    @abc.abstractmethod
    def __init__(self, adapter, args=None, *, loop=SharedLoop):
        """Required constructor signature."""

    @abc.abstractmethod
    async def start(self):
        """Start serving access to devices.

        This method must not return until the devices are accessible over the
        implementations chosen server protocol.  It must be possible to
        immediately attach an AbstractDevice adapter to this server and use it
        without any race conditions.

        For example, if the server is configured to use a TCP port to serve
        devices, the TCP port must be bound and listening for connections when
        this coroutine returns.
        """

    @abc.abstractmethod
    async def stop(self):
        """Stop serving access to devices.

        Subclass **must not** return until the devices are no longer accessible
        over the implementation's chosen server protocol.  There should be no
        race condition where a client is still able to invoke a function on
        this server after stop has returned.  This is important because server
        container running this AbstractDeviceServer may no longer be in a
        state to respond allow for client connections safely.

        Subclasses **must** cleanly disconnect from any devices accessed via
        ``adapter`` before stopping.  It is the job of the ``AbstractDeviceServer``
        to release all of its internal resources.  It is not the job of ``adapter``
        to somehow know that a particular DeviceServer has stopped and free the
        resources associated with that server.

        Subclasses **should** cleanly disconnect any clients when stopped if
        possible, rather than just breaking all sockets, for example.
        """
