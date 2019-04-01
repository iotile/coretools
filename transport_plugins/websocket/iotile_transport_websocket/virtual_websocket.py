# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import base64
import logging
import time
from iotile.core.utilities import SharedLoop
from .generic import ServerCommandError
from iotile.core.hw.transport import VirtualDeviceAdapter
from iotile.core.hw.virtual.virtualdevice import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.hw.virtual.virtualinterface import VirtualIOTileInterface
from iotile.core.exceptions import HardwareError
from .device_server import WebsocketsDeviceServer

_MISSING = object()

class WebSocketVirtualInterface(VirtualIOTileInterface):
    """ Run a simple WebSocket server and provide a virtual interface between it and a virtual device.

    Args:
        args (dict): A dictionary of arguments used to configure this interface.
            Supported args are:

                port (int):
                    The port on which the server will listen (default: 5120)
                    If None is passed, a random port will be chosen and available
                    on the port property after start has finished.

    """
    def __init__(self, args, loop=SharedLoop):
        super(WebSocketVirtualInterface, self).__init__()

        port = args.get('port', _MISSING)
        if port is _MISSING:
            port = 5120
        elif port is not None:
            port = int(args['port'])

        self.chunk_size = 4*1024  # Config chunk size to be 4kb for traces and reports streaming
        self.port = port

        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self._loop = loop

        self._adapter = None

        args = {
            'host': 'localhost',
            'port': None
        }
        self._server = WebsocketsDeviceServer(None, args, loop=loop)

    def start(self, device):
        """Start serving access to this VirtualIOTileDevice

        Args:
            device (VirtualIOTileDevice): The device we will be providing access to
        """

        adapter = VirtualDeviceAdapter(devices=[device])
        self._loop.run_coroutine(adapter.start())

        self._adapter = adapter
        self._server.adapter = adapter

        try:
            self._loop.run_coroutine(self._server.start())
            self.port = self._server.port
            self.logger.info("Websocket server running on port %s", self.port)
        except:
            self._loop.run_coroutine(self._adapter.stop())
            self._adapter = None
            raise

    def stop(self):
        """Safely shut down this interface."""

        self._loop.run_coroutine(self._server.stop())

        if self._adapter is not None:
            self._loop.run_coroutine(self._adapter.stop())
            self._adapter = None
            self._server.adapter = None
