"""Presents a SocketDeviceAdapter that connects via Async Unix Sockets."""

from iotile.core.utilities import SharedLoop

from iotile_transport_socket_lib.generic import SocketDeviceAdapter
from .unixsocket_implementation import UnixClientImplementation

class UnixSocketDeviceAdapter(SocketDeviceAdapter):
    """A device adapter allowing connections to devices over Unix Sockets.

    Args:
        port (str): The path to the unix socket opened by the Device Server
            ex: "/tmp/gateway_socket". Note: This is usually passed in via config file
            in the format "unix:<port>". The "unix:" part is parsed and dropped by the
            HardwareManager
        loop(iotile.core.utilities.BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, port, *, loop=SharedLoop):
        self.implementation = UnixClientImplementation(port, loop)
        SocketDeviceAdapter.__init__(self, self.implementation, loop=loop)
