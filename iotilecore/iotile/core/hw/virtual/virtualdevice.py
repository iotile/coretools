"""Mock IOTile device class for testing other components interactions with IOTile devices
"""

import struct
import inspect
from iotile.core.exceptions import IOTileException, InternalError
from iotile.core.utilities.stoppable_thread import StoppableWorkerThread
from iotile.core.hw.reports.individual_format import IndividualReadingReport
from iotile.core.hw.reports.report import IOTileReading


class RPCNotFoundError(IOTileException):
    """Exception thrown when an RPC is not found
    """
    pass


class RPCInvalidArgumentsError(IOTileException):
    """Exception thrown when an RPC with a fixed parameter format has invalid arguments
    """
    pass


class RPCInvalidReturnValueError(IOTileException):
    """Exception thrown when the return value of an RPC does not conform to its known format
    """
    pass


class RPCInvalidIDError(IOTileException):
    """Exception thrown when an RPC is created with an invalid RPC id
    """
    pass


class TileNotFoundError(IOTileException):
    """Exception thrown when an RPC is sent to a tile that does not exist
    """
    pass


def rpc(address, rpc_id, arg_format, resp_format=None):
    """Decorator to denote that a function implements an RPC with the given ID and address

    The underlying function should be a member function that will take
    individual parameters after the RPC payload has been decoded according
    to arg_format.

    Arguments to the function are decoded from the 20 byte RPC argument payload according
    to arg_format, which should be a format string that can be passed to struct.unpack.

    Similarly, the function being decorated should return an iterable of results that
    will be encoded into a 20 byte response buffer by struct.pack using resp_format as
    the format string.

    The RPC will respond as if it were implemented by a tile at address ``address`` and
    the 16-bit RPC id ``rpc_id``.

    Args:
        address (int): The address of the mock tile this RPC is for
        rpc_id (int): The number of the RPC
        arg_format (string): a struct format code (without the <) for the
            parameter format for this RPC
        resp_format (string): an optional format code (without the <) for
            the response format for this RPC
    """

    if rpc_id < 0 or rpc_id > 0xFFFF:
        raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

    def _rpc_wrapper(func):
        def _rpc_executor(self, payload):
            args = struct.unpack("<{}".format(arg_format), payload)

            resp = func(self, *args)
            if resp_format is not None:
                try:
                    return struct.pack("<{}".format(resp_format), *resp)
                except struct.error as exc:
                    raise RPCInvalidReturnValueError(str(exc))

            return resp

        _rpc_executor.rpc_id = rpc_id
        _rpc_executor.rpc_addr = address
        _rpc_executor.is_rpc = True
        return _rpc_executor

    return _rpc_wrapper


class VirtualIOTileDevice(object):
    """A Virtual IOTile device that can be interacted with as if it were a real one

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (string): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    def __init__(self, iotile_id, name):
        self._rpc_handlers = {}
        self.tiles = set()
        self.name = name
        self.iotile_id = iotile_id
        self.pending_data = False
        self.reports = []
        self.traces = []
        self.script = bytearray()

        self.connected = False
        self.stream_iface_open = False

        # For this device to push streams or tracing data through a VirtualInterface, it
        # needs access to that interface's push channel
        self._push_channel = None
        self._workers = []
        self._started = False

        # Iterate through all of our member functions and see the ones that are
        # RPCS and add them to the RPC handler table
        for name, value in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(value, 'is_rpc'):
                self.register_rpc(value.rpc_addr, value.rpc_id, value)

    def create_worker(self, func, interval, *args, **kwargs):
        """Spawn a worker thread running func

        The worker will be automatically be started when start() is called
        and terminated when stop() is called on this VirtualIOTileDevice.
        This must be called only from the main thread, not from a worker thread.

        create_worker must not be called after stop() has been called.  If it
        is called before start() is called, the thread is started when start()
        is called, otherwise it is called immediately.

        Args:
            func (callable): Either a function that will be called in a loop
                with a sleep of interval seconds with *args and **kwargs or
                a generator function that will be called once and expected to
                yield periodically so that the worker can check if it should
                be killed.
            interval (float): The time interval between invocations of func.
                This should not be 0 so that the thread doesn't peg the CPU
                and should be short enough so that the worker checks if it
                should be killed in a timely fashion.
            *args: Arguments that are passed to func as positional args
            **kwargs: Arguments that are passed to func as keyword args
        """

        thread = StoppableWorkerThread(func, interval, args, kwargs)
        self._workers.append(thread)

        if self._started:
            thread.start()

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        if self._started:
            raise InternalError("The method start() was called twice on VirtualIOTileDevice.")

        self._push_channel = channel
        self._started = True

        for worker in self._workers:
            worker.start()

    def stream(self, report):
        """Stream a report asynchronously

        If no one is listening for the report, the report may be dropped,
        otherwise it will be queued for sending

        Args:
            report (IOTileReport): The report that should be streamed
        """

        if self._push_channel is None:
            return

        self._push_channel.stream(report)

    def stream_realtime(self, stream, value):
        """Stream a realtime value as an IndividualReadingReport

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

    def trace(self, data):
        """Trace data asynchronously

        If no one is listening for traced data, it will be dropped
        otherwise it will be queued for sending.

        Args:
            data (bytearray, string): Unstructured data to trace to any
                connected client.
        """

        if self._push_channel is None:
            return

        self._push_channel.trace(data)

    def stop(self):
        """Synchronously stop this virtual device and any potential workers
        """

        self._started = False

        for worker in self._workers:
            worker.stop()

    def register_rpc(self, address, rpc_id, func):
        """Register an RPC handler with the given info

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            func (callable): The function that should be called to handle the
                RPC.  func is called as func(payload) and must return a single
                string object of up to 20 bytes with its response
        """

        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        self.tiles.add(address)

        code = (address << 8) | rpc_id
        self._rpc_handlers[code] = func

    def call_rpc(self, address, rpc_id, payload=""):
        """Call an RPC by its address and ID

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (string): A byte string of payload parameters up to 20 bytes

        Returns:
            string: The response payload from the RPC
        """
        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        if address not in self.tiles:
            raise TileNotFoundError("Unknown tile address, no registered handler", address=address)

        code = (address << 8) | rpc_id
        if code not in self._rpc_handlers:
            raise RPCNotFoundError("address: {}, rpc_id: {}".format(address, rpc_id))

        return self._rpc_handlers[code](payload)

    def open_rpc_interface(self):
        """Called when someone opens an RPC interface to the device
        """

        pass

    def close_rpc_interface(self):
        """Called when someone closes an RPC interface to the device
        """

        pass

    def open_script_interface(self):
        """Called when someone opens a script interface on this device
        """

        pass

    def open_streaming_interface(self):
        """Called when someone opens a streaming interface to the device

        Returns:
            list: A list of IOTileReport objects that should be sent out
                the streaming interface.
        """

        self.stream_iface_open = True

        return self.reports

    def open_tracing_interface(self):
        """Called when someone opens a tracing interface to the device

        Returns:
            list: A list of bytearray objects that should be sent out
                the tracing interface.
        """

        return self.traces

    def close_tracing_interface(self):
        """Called when someone closes the tracing interface to the device
        """

        pass

    def close_streaming_interface(self):
        """Called when someone closes the streaming interface to the device
        """

        self.stream_iface_open = False

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

        self.script += bytearray(chunk)
