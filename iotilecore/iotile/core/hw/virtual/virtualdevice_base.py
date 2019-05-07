"""Base class for software based iotile devices called virtual devices."""

from iotile.core.exceptions import InternalError, ArgumentError
from ..exceptions import RPCNotFoundError
from ..reports.individual_format import IndividualReadingReport
from ..reports.report import IOTileReading


# pylint: disable=R0902,R0904; backwards compatibility methods and properties already referenced in other modules
class BaseVirtualDevice:
    """A Virtual IOTile device that can be interacted with as if it were a real one.

    This is the base class of all other Virtual IOTile devices.

    This base class does not make any assumptions about how your particular
    subclass is organized and as such is unlikely to be the best parent class
    for any particular use case.  Depending on what you want to do, you may
    want one of the following subclasses:

    - :class:`StandardVirtualDevice`: A general purpose base class for complex
      virtual devices supporting organizing the device into tiles.

    - :class:`SimpleVirtualDevice`: A simpler base class for creating very
      simple virtual devices that just implement a few RPCs without needing to
      put those rpcs into tiles.

    .. important::

        All subclasses must override the function :meth:`call_rpc` to actually
        find and call their RPCs, otherwise the default impementation will
        raise ``RPCNotFoundError`` for all RPCs.  The above two subclasses
        provide appropriate implementations for ``call_rpc``.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
    """

    def __init__(self, iotile_id):
        self.iotile_id = iotile_id

        self._interface_status = dict(connected=False, streaming=False, rpc=False,
                                      tracing=False, script=False, debug=False)

        # For this device to push streams or tracing data through a VirtualInterface, it
        # needs access to that interface's push channel
        self._push_channel = None
        self._started = False

    @property
    def connected(self):
        """Whether someone is connected to the virtual device."""

        return self._interface_status['connected']

    @connected.setter
    def connected(self, value):
        self._interface_status['connected'] = value

    def interface_open(self, name):
        """Check whether the given interface is open.

        Valid interface names are:
         - connected
         - stream
         - trace
         - script
         - debug

        Interfaces are opened by calling open_interface and closed by calling
        close_interface, except for connections which are opened by setting
        the connect propery and closed by clearing the connect property.

        Args:
            name (str): The name of the interface.

        Returns:
            bool: Whether the interface is open.
        """

        if name not in self._interface_status:
            raise ArgumentError("Unkown interface name: %s" % name)

        return self._interface_status[name]

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        if self._started:
            raise InternalError("The method start() was called twice on VirtualIOTileDevice.")

        self._push_channel = channel

    def stop(self):
        """Stop running this virtual device including any worker threads."""

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

        if not self.interface_open('streaming'):
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

    def open_interface(self, name):
        """Open an interface on the device by name.

        Subclasses that want to be notified when an interface is opened can
        declare a method named open_{name}_interface that will be called when
        the given interface is opened.  If such a function is delcared and
        raises an exception, the interface will not be opened.

        Args:
            name (str): The name of the interface to open.
        """

        if name not in self._interface_status:
            raise ArgumentError("Unknown interface name in open_interface: {}".format(name))

        self._interface_status[name] = True

        try:
            iface_open_name = "open_{}_interface".format(name)

            if hasattr(self, iface_open_name):
                open_func = getattr(self, "open_{}_interface".format(name))
                return open_func()

            return None
        except:
            self._interface_status[name] = False
            raise

    def close_interface(self, name):
        """Close an interface on the device by name.

        Subclasses that want to be notified when an interface is closed can
        declare a method named close_{name}_interface that will be called when
        the given interface is opened.  If such a function is declared and
        raises an exception, the interface will still be closed but the
        exception will be raised to the caller.

        Args:
            name (str): The name of the interface to close.
        """

        if name not in self._interface_status:
            raise ArgumentError("Unknown interface name in close_interface: {}".format(name))

        iface_close_name = "close_{}_interface".format(name)

        self._interface_status[name] = False

        if hasattr(self, iface_close_name):
            close_func = getattr(self, iface_close_name)
            close_func()

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

    def call_rpc(self, address, rpc_id, payload=b""):
        """Call an RPC by its address and ID.

        Subclasses must override this function with methods of finding RPCs as
        part of their implementations.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            bytes: The response payload from the RPC
        """

        raise RPCNotFoundError("RPC not found because virtual device did not implement call_rpc method")
