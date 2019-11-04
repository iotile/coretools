"""The Unix Socket Implementation that is used by the adapter and server"""

import logging
import asyncio
from iotile.core.utilities import SharedLoop
from iotile_transport_socket_lib.generic import AbstractSocketServerImplementation
from iotile_transport_socket_lib.generic import AbstractSocketClientImplementation
from iotile_transport_socket_lib.generic.abstract_socket_implementation import AsyncioSocketConnection

class UnixServerImplementation(AbstractSocketServerImplementation):
    """Unix flavor of a socket server

    Args:
        path (str): The path to the Unix Socket that will be opened. The file descriptor that it points
            to will be created by the asyncio.start_unix_server() call
        loop (iotile.core.utilities.BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, path, loop=SharedLoop):
        self.path = path
        self._logger = logging.getLogger(__name__)
        self.loop = loop
        self._manage_connection_cb = None

    async def start_server(self, manage_connection_cb, started_signal):
        """Begin serving. Once started up, set the result of a given signal

        Args:
            manage_connection_cb (function): The function to call when a connection is made. Must accept
                a connection info object to store and later present back to this class to interact
                with that connection
            started_signal (asyncio.future): A future that will be set to True once the server has started
        """

        self._manage_connection_cb = manage_connection_cb
        try:
            server = await asyncio.start_unix_server(self._conn_cb_wrapper, path=self.path, loop=self.loop.get_loop())
            self._logger.debug("Serving on path %s", self.path)
            started_signal.set_result(True)
        except Exception as err:
            self._logger.exception("Error starting unix server on path %s", self.path)
            started_signal.set_exception(err)
            return
        return server

    async def _conn_cb_wrapper(self, reader, writer):
        """A wrapper function to encapsulate the result of a connection into a single object

            Unlike websockets which returns a single connection object, asyncio's servers return
            readers and writers. For simplicity, the reader and writers are stored in an object
            that provides read and write calls

        Args:
            reader (asyncio.StreamReader): The reader returned from the callback
            writer (asyncio.StreamWriter): The writer returned from the callback
        """

        unix_conn = AsyncioSocketConnection(reader, writer, self._logger)
        await self._manage_connection_cb(unix_conn, None)

    async def send(self, con, encoded):
        """Send the byte-encoded data to the given connection

        Args:
            con (AsyncioSocketConnection): The connection to send to
            encoded (bytes): Data to send
        """

        await con.send(encoded)

    async def recv(self, con):
        """Await incoming data from the given connection

        Args:
            con (AsyncioSocketConnection): The connection to receive from
        """
        return await con.recv()

class UnixClientImplementation(AbstractSocketClientImplementation):
    """Unix flavor of a Socket Connection

    Args:
        path (str): Path to the unix socket opened by the Server
        loop (iotile.core.utilities.BackgroundEventLoop): The background event loop we should
            run in.  Defaults to the shared global loop.
    """

    def __init__(self, path, loop=SharedLoop):
        self.path = path
        self._logger = logging.getLogger(__name__)
        self.loop = loop
        self.is_connected = False
        self.con = None

    async def connect(self):
        """Open the connection"""
        reader, writer = await asyncio.open_unix_connection(self.path, loop=self.loop.get_loop())
        self.con = AsyncioSocketConnection(reader, writer, self._logger)
        self._logger.debug("Connected to %s", self.path)

    async def close(self):
        """Close the connection"""
        await self.con.writer.close()
        self.con = None

    def connected(self):
        """Return true if there is an active connection"""
        return bool(self.con)

    async def send(self, encoded):
        """Send the bytes-encoded data

        Args:
            encoded (bytes): Data to send
        """
        await self.con.send(encoded)

    async def recv(self):
        """Await incoming data and return it"""
        return await self.con.recv()
