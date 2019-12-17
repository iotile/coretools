"""Presents a SocketDeviceServer that serves via Async Unix Sockets."""

from iotile.core.utilities import SharedLoop
from iotile_transport_socket_lib.generic import SocketDeviceServer
from .unixsocket_implementation import UnixServerImplementation

class UnixSocketDeviceServer(SocketDeviceServer):
    """A device server for connections to multiple devices via a SocketServer

    This class connects to an AbstractDeviceAdapter and serves it over
    Unix Sockets. Currently the support arguments to pass in args are:

    - ``path``: The path to the Unix Socket that will be opened. The file descriptor that it points
        to will be created by the UnixServerImplementation's asyncio.start_unix_server() call

    Args:
        adapter (AbstractDeviceAdapter): The device adapter that we should use
            to find devices.
        args (dict): Arguments to this device server.
        loop(iotile.core.utilities.BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, adapter, args=None, *, loop=SharedLoop):
        path = args.get('path', None)
        self.implementation = UnixServerImplementation(path, loop)
        SocketDeviceServer.__init__(self, adapter, self.implementation, args, loop=loop)
