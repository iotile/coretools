"""A convenience subclass for simple virtual devices.

These devices do not include support for tiles or complex modularity but
instead just queue a few streams and/or traces when a user connects to them and
support running periodic background tasks using coroutine based workers that
are triggered on a schedule.

They are useful for writing simple, repeatable tests.
"""

from .virtualdevice_base import BaseVirtualDevice
from .base_runnable import BaseRunnable
from .common_types import rpc

class SimpleVirtualDevice(BaseVirtualDevice, BaseRunnable):
    """A simple virtual device with a tile "fake" tile at address 8.

    This class implements the required controller status RPC that allows
    matching it with a proxy object.  You can define period worker functions
    that add simple interactivity using the :meth:`start_worker` method.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (str): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    __NO_EXTENSION__ = True

    def __init__(self, iotile_id, name):
        BaseVirtualDevice.__init__(self, iotile_id)
        BaseRunnable.__init__(self)

        self.name = name.encode('utf-8')
        self.reports = []
        self.traces = []
        self.script = bytearray()

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

    def open_streaming_interface(self):
        """Handler called when the streaming interface is opened.

        If a list of reports is returned, those reports are streamed out of
        the device immediately.
        """

        return self.reports

    def open_tracing_interface(self):
        """Handler called when the tracing interface is opened.

        If a list of bytes-like object is returned, they will be traced out of
        the tracing interface immediately.
        """

        return self.traces

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads.
        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(SimpleVirtualDevice, self).start(channel)
        self.start_workers()

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        self.stop_workers()
        super(SimpleVirtualDevice, self).stop()
