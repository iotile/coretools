"""Generic implementation of serving access to a device over websockets."""


from iotile.core.utilities import SharedLoop
from iotile_transport_socket_lib.generic import SocketDeviceServer
from .websocket_implementation import WebsocketServerImplementation


_MISSING = object()

class WebSocketDeviceServer(SocketDeviceServer):
    """A device server for connections to multiple devices via a SocketServer

    This class connects to an AbstractDeviceAdapter and serves it over
    Websockets. Currently the support arguments to pass in args are:

    - ``host``: The host name to serve on, defaults to 127.0.0.1
    - ``port``: The port name to serve on, defaults to a random port if not specified.
      If a random port is used, its value can be read on the ``port`` property after
      start() has completed.

    Args:
        adapter (AbstractDeviceAdapter): The device adapter that we should use
            to find devices.
        args (dict): Arguments to this device server.
        loop (BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, adapter, args=None, *, loop=SharedLoop):
        host = args.get('host', '127.0.0.1')
        port_suggestion = args.get('port', None)
        self.implementation = WebsocketServerImplementation(host, port_suggestion)
        SocketDeviceServer.__init__(self, adapter, self.implementation, args, loop=loop)
        self.port = None
