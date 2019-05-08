"""A convenience subclass for simple virtual devices.

These devices do not include support for tiles or complex modularity but
instead just queue a few streams and/or traces when a user connects to them and
support running periodic background tasks using coroutine based workers that
are triggered on a schedule.

They are useful for writing simple, repeatable tests.
"""

import inspect
from iotile.core.utilities import SharedLoop
from ..exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from .virtualdevice_base import BaseVirtualDevice
from .periodic_worker import _PeriodicWorkerMixin
from .common_types import rpc, RPCDispatcher


class SimpleVirtualDevice(BaseVirtualDevice, _PeriodicWorkerMixin):
    """A simple virtual device with a "fake" tile at address 8.

    This class implements the required controller status RPC that allows
    matching it with a proxy object.  You can define periodic worker functions
    that add simple interactivity using the :meth:`start_worker` method.

    If you want to add extra RPCs, you can do so by decorating your rpc
    implementation with an ``@rpc`` decorator or by adding them dynamically
    using :meth:`register_rpc`.

    The default implementation will respond to RPC 8:0004 with a fixed tile
    name for the tile at address 8 based on the ``name`` you pass in to the
    __init__ function.  This allows for the creation of matched proxy objects
    that correspond with your simple device.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (str): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
        loop (BackgroundEventLoop): The loop we should use for running background
            tasks. Defaults to the global SharedLoop.
            *This must be passed as a keyword agument.*
    """

    __NO_EXTENSION__ = True

    def __init__(self, iotile_id, name, *, loop=SharedLoop):
        BaseVirtualDevice.__init__(self, iotile_id, loop=loop)
        _PeriodicWorkerMixin.__init__(self)

        self.name = name.encode('utf-8')
        self.reports = []
        self.traces = []
        self.script = bytearray()

        # Iterate through all of our member functions and see the ones that are
        # RPCS and add them to the RPC handler table
        self._rpc_overlays = {}
        for _name, value in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(value, 'is_rpc'):
                self.register_rpc(value.rpc_addr, value.rpc_id, value)

    def register_rpc(self, address, rpc_id, func):
        """Register a single RPC handler with the given info.

        This function can be used to directly register individual RPCs,
        rather than delegating all RPCs at a given address to a virtual
        Tile.

        If calls to this function are mixed with calls to add_tile for
        the same address, these RPCs will take precedence over what is
        defined in the tiles.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            func (callable): The function that should be called to handle the
                RPC.  func is called as func(payload) and must return a single
                string object of up to 20 bytes with its response
        """

        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        if address not in self._rpc_overlays:
            self._rpc_overlays[address] = RPCDispatcher()

        self._rpc_overlays[address].add_rpc(rpc_id, func)

    async def async_rpc(self, address, rpc_id, payload=b""):
        """Call an RPC by its address and ID.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            bytes: The response payload from the RPC
        """

        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        if address not in self._rpc_overlays:
            raise TileNotFoundError("Unknown tile address, no registered handler", address=address)

        overlay = self._rpc_overlays.get(address, None)

        if overlay is not None and overlay.has_rpc(rpc_id):
            resp = overlay.call_rpc(rpc_id, payload)
            if inspect.isawaitable(resp):
                resp = await resp

            return resp

        raise RPCNotFoundError("Could not find RPC 0x%X at address %d" % (rpc_id, address))


    @rpc(8, 0x0004, "", "H6sBBBB")
    def status(self):
        """RPC returning a tile name to match against an installed proxy."""

        status = (1 << 1) | (1 << 0) # Configured and running

        return [0xFFFF, self.name, 1, 0, 0, status]

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

        self.script += bytearray(chunk)

    def _open_streaming_interface(self):
        """Handler called when the streaming interface is opened.

        If a list of reports is returned, those reports are streamed out of
        the device immediately.
        """

        return self.reports

    def _open_tracing_interface(self):
        """Handler called when the tracing interface is opened.

        If a list of bytes-like object is returned, they will be traced out of
        the tracing interface immediately.
        """

        return self.traces

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads.

        Args:
            channel (AbstractAsyncDeviceChannel): channel to use to push asynchronous
                events to a connected client.
        """

        super(SimpleVirtualDevice, self).start(channel)
        self.start_workers()

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        self.stop_workers()
        super(SimpleVirtualDevice, self).stop()
