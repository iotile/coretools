"""Abstract base class for different socket transport implementations

Allows the AbstractDeviceAdapter and Servers to communicate via any different
protocols depending onsystem architect's choice

The functions will contain implementation details specific to the protocol.
For example, Unix Socket's send and receive functions will encode and send the
size of each transmission first and call the asyncio StreamReader and Writer
send and receive functions.
"""

import abc
import struct
import asyncio


class AsyncioSocketConnection:
    """Paired read and write commands for an active Socket Connection

    Args:
        reader (asyncio.StreamReader): The reader returned from the connect command or callback
        writer (asyncio.StreamWriter): The writer returned from the connect command or callback
        logger (logging.Logger): The logger to use (Since this is used by both the Server and Client, the
            logger should be that of the Server or Client)
    """

    _ARCHMAGIC = "ARCH".encode()
    _HEADERFORMAT = '4sL'
    def __init__(self, reader, writer, logger):
        self.reader = reader
        self.writer = writer
        self._logger = logger

    async def send(self, encoded):
        """Send encoded byte data. First send a header with the data's length, then the data itself
        Return once data in the buffer has been drained

        Args:
            encoded (bytes): Encoded data to send
        """
        try:
            packed_header = struct.pack(self._HEADERFORMAT, self._ARCHMAGIC, len(encoded))
            self.writer.write(packed_header)
            self.writer.write(encoded)
            await self.writer.drain()

        except Exception:
            raise ConnectionError from Exception

    async def recv(self):
        """Await incoming data, return the encoded bytes

        Returns:
            bytes: Encoded data object
        """
        packed_header = await self.reader.read(struct.calcsize(self._HEADERFORMAT))
        magic, encoded_len = struct.unpack(self._HEADERFORMAT, packed_header)

        if magic != self._ARCHMAGIC:
            raise struct.error

        encoded = await self.reader.read(encoded_len)
        return encoded


class AbstractSocketServerImplementation(abc.ABC):
    """Abstract Socket Server"""

    @abc.abstractmethod
    def start_server(self, manage_connection_cb, started_signal):
        """Begin serving. Once started up, set the result of a given signal

        Args:
            manage_connection_cb (function): The function to call when a connection is made. Must accept
                a connection info object to store and later present back to this class to interact
                with that connection
            started_signal (asyncio.future): A future that will be set once the server is started.
        """

    @abc.abstractmethod
    async def send(self, con, encoded):
        """Send the byte-encoded data to the given connection

        Args:
            con (a connection object): The connection to send to. The implementation
                must know how to use this object to send the data to the right target
            encoded (bytes): Data to send
        """

    @abc.abstractmethod
    async def recv(self, con):
        """Await incoming data from the given connection

        Args:
            con (a connection object): The connection to receive from.
                The implementation must know how to use this object
        """

class AbstractSocketClientImplementation(abc.ABC):
    """Abstract Socket Client"""

    @abc.abstractmethod
    async def connect(self):
        """Open the connection"""

    @abc.abstractmethod
    async def close(self):
        """Close the connection"""

    @abc.abstractmethod
    def connected(self):
        """Return true if there is an active connection"""

    @abc.abstractmethod
    async def send(self, packed):
        """Send the bytes-encoded data

        Args:
            packed(bytes): Data to send
        """

    @abc.abstractmethod
    async def recv(self):
        """Await incoming data and return it"""
        