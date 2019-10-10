# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import websockets
import asyncio

class WebsocketServerImplementation:

    def __init__(self, host='127.0.0.1', port=None):
        self.host = host
        self.port = port
        self._logger = logging.getLogger(__name__)

    async def connect(self, manage_connection_cb, started_signal):
        try:
            server = await websockets.serve(manage_connection_cb, self.host, self.port)
            if self.port is None:
                self.port = server.sockets[0].getsockname()[1]
            started_signal.set_result(self.port)
        except Exception as err:
            self._logger.exception("Error starting server on host %s, port %s", self.host, self.port)
            started_signal.set_exception(err)
            return
        return server

    async def send(self, con, encoded):
        try:
            await con.send(encoded)
        except websockets.exceptions.ConnectionClosed:
            raise ConnectionError

    async def recv(self, con):
        return await con.recv()

class WebsocketClientImplementation:

    def __init__(self, path):
        self.path = path
        self._con = None

    async def start(self):
        self._con = await websockets.connect(self.path)

    async def close(self):
        await self._con.close()
        self._con = None

    def connected(self):
        if self._con:
            return True
        else:
            return False

    async def send(self, packed):
       await self._con.send(packed)

    async def recv(self):
        return await self._con.recv()