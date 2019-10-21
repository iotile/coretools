# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import asyncio
import struct
from iotile.core.utilities import SharedLoop
from iotile_transport_socket_lib.generic.packing import pack, unpack

ARCHMAGIC = "ARCH".encode()
HEADERFORMAT = '4sL'

class UnixSocketConnection:
    def __init__(self, reader, writer, logger):
        self.reader = reader
        self.writer = writer
        self._logger = logger

    async def send(self, encoded):
        try:
            packed_header = struct.pack(HEADERFORMAT, ARCHMAGIC, len(encoded))
            self.writer.write(packed_header)
            self.writer.write(encoded)
            await self.writer.drain()
            self._logger.debug("Sent %d bytes: %s", len(encoded), unpack(encoded))

        except Exception:
            raise ConnectionError

    async def _reset_read_buffer(self, packed_header):
        self._logger.error("Invalid header. Read %b", packed_header)
        await self.reader.read()

    async def recv(self):
        encoded = ""
        while encoded == "":
            packed_header = await self.reader.read(struct.calcsize(HEADERFORMAT))
            try:
                magic, encoded_len = struct.unpack(HEADERFORMAT, packed_header)
            except struct.error:
                await self._reset_read_buffer(packed_header)
                continue

            if magic != ARCHMAGIC:
                await self._reset_read_buffer(packed_header)
                continue

            encoded = await self.reader.read(encoded_len)
            self._logger.debug("Read %d bytes: %s", len(encoded), unpack(encoded))
            return encoded


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
        unix_conn = UnixSocketConnection(reader, writer, self._logger)
        await self._manage_connection_cb(unix_conn, None)

    async def send(self, con, encoded):
        await con.send(encoded)

    async def recv(self, con):
        return await con.recv()

class UnixClientImplementation:

    def __init__(self, path, loop=SharedLoop):
        self.path = path
        self._logger = logging.getLogger(__name__)
        self.loop = loop
        self.is_connected = False
        self.con = None

    async def start(self):
        reader, writer = await asyncio.open_unix_connection(self.path, loop=self.loop.get_loop())
        self.con = UnixSocketConnection(reader, writer, self._logger)
        self._logger.debug("Connected to %s", self.path)

    async def close(self):
        await self.con.writer.close()
        self.con = None

    def connected(self):
        return bool(self.con)

    async def send(self, encoded):
        await self.con.send(encoded)

    async def recv(self):
        return await self.con.recv()
