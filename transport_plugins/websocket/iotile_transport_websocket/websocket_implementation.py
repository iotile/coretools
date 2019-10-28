# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import websockets
import asyncio

from iotile_transport_socket_lib.generic import AbstractSocketServerImplementation
from iotile_transport_socket_lib.generic import AbstractSocketClientImplementation

class WebsocketServerImplementation(AbstractSocketServerImplementation):
    """Websocket flavor of a socket server

    Args:
        host (str): The host name to serve on, defaults to 127.0.0.1
        port (str): The port name to serve on, defaults to a random port if not specified.

    """
    def __init__(self, host='127.0.0.1', port=None):
        self.host = host
        self.port = port
        self._logger = logging.getLogger(__name__)

    async def start_server(self, manage_connection_cb, started_signal):
        """Begin serving. Once started up, set the result of a given signal to the server's port

        Args:
            manage_connection_cb (function): The function to call when a connection is made. Must accept
                a connection info object to store and later present back to this class to interact
                with that connection
            started_signal (asyncio.future): A future that will be set to True once the server has started
        """
        try:
            server = await websockets.serve(manage_connection_cb, self.host, self.port)
            if self.port is None:
                self.port = server.sockets[0].getsockname()[1]
            started_signal.set_result(True)
        except Exception as err:
            self._logger.exception("Error starting server on host %s, port %s", self.host, self.port)
            started_signal.set_exception(err)
            return
        return server

    async def send(self, con, encoded):
        """Send the byte-encoded data to the given connection

        Args:
            con (websockets.WebSocketServerProtocol): The connection to send to
            encoded (bytes): Data to send
        """
        try:
            await con.send(encoded)
        except websockets.exceptions.ConnectionClosed:
            raise ConnectionError

    async def recv(self, con):
        """Await incoming data from the given connection

        Args:
            con (websockets.WebSocketServerProtocol): The connection to receive from
        """
        return await con.recv()

class WebsocketClientImplementation(AbstractSocketClientImplementation):
    """Websockets flavor of a Socket Connection

    Args:
        sockaddr (str): A target for the WebSocket client to connect to in form of
            server:port.  For example, "localhost:5120".
    """

    def __init__(self, sockaddr):
        self.sockaddr = sockaddr
        self._con = None

    async def connect(self):
        """Open the connection"""
        self._con = await websockets.connect(self.sockaddr)

    async def close(self):
        """Close the connection"""
        await self._con.close()
        self._con = None

    def connected(self):
        """Return true if there is an active connection"""
        return bool(self._con)

    async def send(self, packed):
        """Send the bytes-encoded data

        Args:
            packed(bytes): Data to send
        """
        await self._con.send(packed)

    async def recv(self):
        """Await incoming data and return it"""
        return await self._con.recv()
        