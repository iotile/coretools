# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import asyncio
from iotile.core.utilities import SharedLoop
from iotile_transport_socket_lib.generic.packing import pack, unpack

class UnixServerConnection:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

class UnixServerImplementation:

    def __init__(self, path, loop=SharedLoop):
        self.path = path
        self._logger = logging.getLogger(__name__)
        self._logger.debug("Hello?")
        self.loop = loop
        self._manage_connection_cb = None

    async def connect(self, manage_connection_cb, started_signal):
        self._manage_connection_cb = manage_connection_cb
        try:
            self._logger.debug("Serving on path %s", self.path)
            server = await asyncio.start_unix_server(self._conn_cb_wrapper, path=self.path, loop=self.loop.get_loop())
            started_signal.set_result(True)
        except Exception as err:
            self._logger.exception("Error starting unix server on path %s", self.path)
            started_signal.set_exception(err)
            return
        return server

    async def _conn_cb_wrapper(self, reader, writer):
        self._logger.debug("reader: %s, writer: %s", str(reader), str(writer))
        unix_conn = UnixServerConnection(reader, writer)
        await self._manage_connection_cb(unix_conn, None)

    async def send(self, con, encoded):
        try:
            con.writer.write(encoded)
            con.writer.write('\n'.encode())
            await con.writer.drain()
            self._logger.debug("Sent %d bytes: %s", len(encoded), unpack(encoded))

        except Exception:
            raise ConnectionError

    async def recv(self, con):
        encoded = await con.reader.readline()
        encoded = encoded[:-1]
        self._logger.debug("Read %d bytes: %s", len(encoded), unpack(encoded))
        return encoded

class UnixClientImplementation:

    def __init__(self, path, loop=SharedLoop):
        self.path = path
        self._reader = None
        self._writer = None
        self._logger = logging.getLogger(__name__)
        self.loop = loop
        self.is_connected = False

    async def start(self):
        self._reader, self._writer = await asyncio.open_unix_connection(self.path, loop=self.loop.get_loop())
        self._logger.debug("Connected to %s", self.path)
        self.is_connected = True

    async def close(self):
        await self._reader.close()
        await self._writer.close()
        self._writer = None
        self._reader = None
        self.is_connected = False

    def connected(self):
        return self.is_connected

    async def send(self, encoded):
        try:
            self._writer.write(encoded)
            self._writer.write('\n'.encode())
            await self._writer.drain()
            self._logger.debug("Sent %d bytes: %s", len(encoded), unpack(encoded))
        except Exception:
            raise ConnectionError

    async def recv(self):
        encoded = await self._reader.readline()
        encoded = encoded[:-1]
        self._logger.debug("Read %d bytes: %s", len(encoded), unpack(encoded))
        return encoded
