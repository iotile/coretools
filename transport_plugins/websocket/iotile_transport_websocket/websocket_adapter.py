# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.utilities import SharedLoop

from iotile_transport_socket_lib.generic import SocketDeviceAdapter
from .websocket_implementation import WebsocketClientImplementation


class WebSocketDeviceAdapter(SocketDeviceAdapter):
    """ A device adapter allowing connections to devices over WebSockets.

    Args:
        port (string): A target for the WebSocket client to connect to in form of
            server:port.  For example, "localhost:5120".
        loop (iotile.core.utilities.BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, port, *, loop=SharedLoop):
        sockaddr = "ws://{0}/iotile/v3".format(port)
        self.implementation = WebsocketClientImplementation(sockaddr)

        SocketDeviceAdapter.__init__(self, self.implementation, loop=loop)
