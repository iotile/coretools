"""Base class for software based iotile devices called virtual devices."""

import abc
import inspect
import logging
from iotile.core.exceptions import InternalError, ArgumentError
from iotile.core.utilities import SharedLoop
from ..exceptions import RPCNotFoundError, DevicePushError
from ..reports.individual_format import IndividualReadingReport
from ..reports.report import IOTileReading
from .common_types import RPCDeclaration, pack_rpc_payload, unpack_rpc_payload


class AbstractAsyncDeviceChannel(abc.ABC):
    """Abstract class for virtual devices to push events to clients.

    When a virtual device is started, it is passed a subclass of this base
    class in its :meth:`BaseVirtualDevice.start` method and it can use that
    class to push reports via the streaming interface, tracing data via the
    tracing interface, broadcast data or to disconnect the client forcibly.

    This base class just defines the methods that must be provided and their
    signatures.  Each method must return an awaitable object.
    """

    @abc.abstractmethod
    def stream(self, report):
        """Stream a report to the client.

        This method must yield until the report has been successfully sent or
        queued for sending in order to propogate backpressure to callers that
        are streaming reports faster than the DeviceServer can actually send
        them.

        If the report is not able to be sent, an instance of :class:`StreamingError`
        must be raised.

        Args:
            report (IOTileReport): The report that should be streamed out of the
                device.  If the report is a subclass of :class:`BroadcastReport`,
                it will be broadcast instead of streamed.

        Returns:
            awaitable: An awaitable that will finish when the report has been sent.

            Note that there is no gurantee that the report has succesfully
            reached the client when this method returns since many things
            could have gone wrong in the air or on the client's software.
            This response is purely useful for flow control.

        Raises:
            DevicePushError: The report could not be streamed/queued for streaming.
        """

    @abc.abstractmethod
    def trace(self, data):
        """Send binary tracing data to the client.

        This method must yield until the tracing data is successfully sent or
        queued for sending in order to propogate backpressure to callers that
        are tracing data faster than the DeviceServer can actually send it.

        If the data cannot be sent or queued, an instance of :class:`TracingError`
        must be raised.

        Args:
            data (bytes): The raw data that should be sent out of the tracing interface

        Returns:
            awaitable: An awaitable that will finish when the tracing data has been sent.

            Note that there is no gurantee that the data has succesfully
            reached the client when this method returns since many things
            could have gone wrong in the air or on the client's software. This
            response is purely useful for flow control.

        Raises:
            DevicePushError: The tracing data could not be send/queued for sending.
        """

    @abc.abstractmethod
    def disconnect(self):
        """Forcibly disconnect the connected client.

        In order to prevent race conditions, this method should not return
        until the client has been disconnected.

        Returns:
            awaitable: An awaitable that resolves when the client has been disconnected.

        Raises:
            DevicePushError: If there is no client connected or they could not be disconnected.
        """


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

    In order to be able to dynamically created by :class:`VirtualDeviceAdapter`,
    all BaseVirtualDevice subclasses must have the following __init__ signature::

        __init__(self, config, *, loop=SharedLoop)

    The ``config`` parameter is a dictionary of arguments that can be used in
    any way the virtual device class likes to configure itself.  If the device
    needs explicit access to a BackgroundEventLoop, it can declare a keyword
    parameter named ``loop``, which will be filled in with the appropriate
    ``BackgroundEventLoop`` that the ``VirtualDeviceAdapter`` is using
    internally.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        loop (BackgroundEventLoop): The event loop to use to run coroutines.
    """

    def __init__(self, iotile_id, loop=SharedLoop):
        self.iotile_id = iotile_id

        self._interface_status = dict(connected=False, streaming=False, rpc=False,
                                      tracing=False, script=False, debug=False)

        # For this device to push streams or tracing data through a VirtualInterface, it
        # needs access to that interface's push channel
        self._push_channel = None
        self._started = False
        self._logger = logging.getLogger(__name__)
        self._loop = loop

    @property
    def connected(self):
        """Whether someone is connected to the virtual device."""

        return self._interface_status['connected']

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
        """Start running this virtual device.

        Args:
            channel (AbstractAsyncDeviceChannel): A channel that can be used by the device
                to push events asynchronously to an attached client.
        """

        if self._started:
            raise InternalError("The method start() was called twice on VirtualIOTileDevice.")

        self._push_channel = channel
        self._started = True

    def stop(self):
        """Stop running this virtual device."""

        if not self._started:
            raise InternalError("Stop called without start() first being called")

        self._started = False

    async def connect(self):
        """Connect to this virtual device."""

        if self.connected:
            raise InternalError("connect() was called but someone was already connected")

        await self.open_interface('connected')

    async def disconnect(self):
        """Disconnect from this virtual device.

        Any other interfaces that are opened on the device will be closed
        automatically before the disconnect routine completes.  After this
        method finishes successfully, you will be able to connect to the
        device again.
        """

        if not self.connected:
            raise InternalError("disconnect() was called without a connection")

        for key in ('streaming', 'tracing', 'debug', 'script', 'rpc'):
            if self.interface_open(key):
                await self.close_interface(key)

        await self.close_interface('connected')

    async def stream(self, report):
        """Stream a report asynchronously.

        If no one is listening for the report, the report may be dropped,
        otherwise it will be queued for sending

        Args:
            report (IOTileReport): The report that should be streamed
            callback (callable): Optional callback to get notified when
                this report is actually sent.

        Returns:
            awaitable: Resolves when the streaming finishes
        """

        if self._push_channel is None:
            raise DevicePushError("No push channel configured for device")

        await self._push_channel.stream(report)

    async def stream_realtime(self, stream, value):
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

    async def trace(self, data):
        """Trace data asynchronously.

        If no one is listening for traced data, it will be dropped
        otherwise it will be queued for sending.

        Args:
            data (bytes): Unstructured data to trace to any
                connected client.
        """

        if self._push_channel is None:
            raise DevicePushError("No push channel configured for device")

        await self._push_channel.trace(data)

    async def open_interface(self, name):
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
            iface_open_name = "_open_{}_interface".format(name)

            if hasattr(self, iface_open_name):
                open_func = getattr(self, iface_open_name)
                res = open_func()
                if inspect.isawaitable(res):
                    res = await res

                return res

            return None
        except:
            self._interface_status[name] = False
            raise

    async def close_interface(self, name):
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

        iface_close_name = "_close_{}_interface".format(name)

        self._interface_status[name] = False

        if hasattr(self, iface_close_name):
            close_func = getattr(self, iface_close_name)
            res = close_func()
            if inspect.isawaitable(res):
                await res

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

    async def async_rpc(self, address, rpc_id, payload=b""):
        """Call an RPC by its address and ID.

        Subclasses must override this function with methods of finding RPCs as
        part of their implementations.  This method is designed to be called
        from a DeviceAdapter subclass and passed binary encoded arguments.

        It is not intended to be called directly by users.  If you are looking
        for a simple way to test out the rpcs provided by a VirtualDevice
        without needing an event loop or worrying about packing, you should
        use :meth:`simple_rpc`.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            bytes: The response payload from the RPC
        """

        raise RPCNotFoundError("RPC not found because virtual device did not implement call_rpc method")

    def simple_rpc(self, address, rpc_id, *args, **kwargs):
        """Synchronously dispatch an RPC inside this device.

        This function is meant to be used for testing purposes.  It is not
        an async method and indeed cannot be called from an event loop since
        it synchronously blocks until the RPC finished before returning.

        Callers of this function must know the argument spec of the RPC that
        they are trying to call and expected return value.

        Args:
            address (int): The address of the tile that has the RPC.
            rpc_id (int or RPCDeclaration): The 16-bit id of the rpc we want
                to call. If an RPCDeclaration is passed then arg_format and
                result_format are not required since they are included in the
                RPCDeclaration.
            *args: Any required arguments for the RPC as python objects.
            **kwargs: Only two keyword arguments are supported:
                - arg_format: A format specifier for the argument list
                - result_format: A format specifier for the result

        Returns:
            list: A list of the decoded response members from the RPC.
        """

        if isinstance(rpc_id, RPCDeclaration):
            arg_format = rpc_id.arg_format
            resp_format = rpc_id.resp_format
            rpc_id = rpc_id.rpc_id
        else:
            arg_format = kwargs.get('arg_format', None)
            resp_format = kwargs.get('resp_format', None)

        arg_payload = b''

        if arg_format is not None:
            arg_payload = pack_rpc_payload(arg_format, args)

        self._logger.debug("Sending rpc to %d:%04X, payload=%s", address, rpc_id, args)

        resp_payload = self._loop.run_coroutine(self.async_rpc(address, rpc_id, arg_payload))
        if resp_format is None:
            return []

        return unpack_rpc_payload(resp_format, resp_payload)
