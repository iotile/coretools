"""Mock IOTile device class for testing other components interactions with IOTile devices
"""

import inspect
from iotile.core.exceptions import InternalError, ArgumentError
from iotile.core.hw.reports.individual_format import IndividualReadingReport
from iotile.core.hw.reports.report import IOTileReading
from .base_runnable import BaseRunnable
from .common_types import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError, RPCDispatcher, rpc  # pylint: disable=W0611; rpc import needed for backwards compatibility


# pylint: disable=R0902,R0904; backwards compatibility methods and properties already referenced in other modules
class VirtualIOTileDevice(BaseRunnable):
    """A Virtual IOTile device that can be interacted with as if it were a real one.

    This is the base class of all other Virtual IOTile devices.  It allows defining
    RPCs directly using decorators and the `register_rpc` function.  Subclasses
    implement virtual tiles that modularize building complex virtual devices from
    reusable pieces.

    This class also implements the required controller status RPC that allows
    matching it with a proxy object.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (string): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    def __init__(self, iotile_id, name):
        super(VirtualIOTileDevice, self).__init__()

        self._rpc_overlays = {}
        self._tiles = {}

        self.name = name.encode('utf-8')
        self.iotile_id = iotile_id
        self.reports = []
        self.traces = []
        self.script = bytearray()

        self._interface_status = {}
        self._interface_status['connected'] = False
        self._interface_status['stream'] = False
        self._interface_status['trace'] = False
        self._interface_status['script'] = False
        self._interface_status['rpc'] = False

        # For this device to push streams or tracing data through a VirtualInterface, it
        # needs access to that interface's push channel
        self._push_channel = None

        # Iterate through all of our member functions and see the ones that are
        # RPCS and add them to the RPC handler table
        for _name, value in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(value, 'is_rpc'):
                self.register_rpc(value.rpc_addr, value.rpc_id, value)

    @property
    def connected(self):
        """Whether someone is connected to the virtual device."""

        return self._interface_status['connected']

    @connected.setter
    def connected(self, value):
        self._interface_status['connected'] = value

    @property
    def stream_iface_open(self):
        """Whether the streaming interface is opened.

        Deprecated:
            3.14.5: Use interface_open('stream') instead
        """

        return self._interface_status['stream']

    @property
    def trace_iface_open(self):
        """Whether the tracing interface is opened.

        Deprecated:
            3.14.5: Use interface_open('trace') instead
        """

        return self._interface_status['trace']

    @property
    def pending_data(self):
        """Whether there are streaming reports waiting to be sent."""

        return len(self.reports) > 0

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        if self._started:
            raise InternalError("The method start() was called twice on VirtualIOTileDevice.")

        self._push_channel = channel
        self.start_workers()

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        self.stop_workers()

    def stream(self, report, callback=None):
        """Stream a report asynchronously.

        If no one is listening for the report, the report may be dropped,
        otherwise it will be queued for sending

        Args:
            report (IOTileReport): The report that should be streamed
            callback (callable): Optional callback to get notified when
                this report is actually sent.
        """

        if self._push_channel is None:
            return

        self._push_channel.stream(report, callback=callback)

    def stream_realtime(self, stream, value):
        """Stream a realtime value as an IndividualReadingReport.

        If the streaming interface of the VirtualInterface this
        VirtualDevice is attached to is not opened, the realtime
        reading may be dropped.

        Args:
            stream (int): The stream id to send
            value (int): The stream value to send
        """

        if not self.stream_iface_open:
            return

        reading = IOTileReading(0, stream, value)

        report = IndividualReadingReport.FromReadings(self.iotile_id, [reading])
        self.stream(report)

    def trace(self, data, callback=None):
        """Trace data asynchronously.

        If no one is listening for traced data, it will be dropped
        otherwise it will be queued for sending.

        Args:
            data (bytearray, string): Unstructured data to trace to any
                connected client.
            callback (callable): Optional callback to get notified when
                this data is actually sent.
        """

        if self._push_channel is None:
            return

        self._push_channel.trace(data, callback=callback)

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

    def call_rpc(self, address, rpc_id, payload=b""):
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

        if address not in self._rpc_overlays and address not in self._tiles:
            raise TileNotFoundError("Unknown tile address, no registered handler", address=address)

        overlay = self._rpc_overlays.get(address, None)
        tile = self._tiles.get(address, None)
        if overlay is not None and overlay.has_rpc(rpc_id):
            return overlay.call_rpc(rpc_id, payload)
        elif tile is not None and tile.has_rpc(rpc_id):
            return tile.call_rpc(rpc_id, payload)

        raise RPCNotFoundError("Could not find RPC 0x%X at address %d" % (rpc_id, address))

    def add_tile(self, address, tile):
        """Add a tile to handle all RPCs at a given address.

        Args:
            address (int): The address of the tile
            tile (RPCDispatcher): A tile object that inherits from RPCDispatcher
        """

        if address in self._tiles:
            raise ArgumentError("Tried to add two tiles at the same address", address=address)

        self._tiles[address] = tile

    def open_rpc_interface(self):
        """Called when someone opens an RPC interface to the device."""

        self._interface_status['rpc'] = True

    def close_rpc_interface(self):
        """Called when someone closes an RPC interface to the device."""

        self._interface_status['rpc'] = False

    def open_script_interface(self):
        """Called when someone opens a script interface on this device."""

        self._interface_status['script'] = True

    def close_script_interface(self):
        """Called when someone closes a script interface on this device."""

        self._interface_status['script'] = False

    def open_streaming_interface(self):
        """Called when someone opens a streaming interface to the device.

        Returns:
            list: A list of IOTileReport objects that should be sent out
                the streaming interface.
        """

        self._interface_status['stream'] = True
        return self.reports

    def close_streaming_interface(self):
        """Called when someone closes the streaming interface to the device."""

        self._interface_status['stream'] = False

    def open_tracing_interface(self):
        """Called when someone opens a tracing interface to the device.

        Returns:
            list: A list of bytearray objects that should be sent out
                the tracing interface.
        """

        self._interface_status['trace'] = True
        return self.traces

    def close_tracing_interface(self):
        """Called when someone closes the tracing interface to the device."""

        self._interface_status['trace'] = False

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

        self.script += bytearray(chunk)
