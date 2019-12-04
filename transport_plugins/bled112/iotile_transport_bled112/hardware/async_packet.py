from threading import Thread, Event
import struct
import logging
from serial import SerialException


class BGAPIPacket:
    __slots__ = ['class_', 'cmd', 'event', 'payload', 'conn']

    _CONN_EVENTS = frozenset([
        (4, 1), (4, 2), (4, 4), (4, 5), (3, 0), (3, 4)
    ])

    def __init__(self, header, payload):
        flags, class_, command = struct.unpack("<BxBB", header)

        self.class_ = class_
        self.event = flags == 0x80
        self.cmd = command
        self.payload = payload

        if self.event and (class_, command) in self._CONN_EVENTS:
            self.conn = payload[0]
        else:
            self.conn = None


class ConnectionPacket(BGAPIPacket):
    """Special packet for connection events.

    These events are reused in a number of contexts with flags set to
    indicate different uses.  We need to filter on those flags in order
    to react only to, for example, new connections.
    """

    __slots__ = ['new', 'connected']

    def __init__(self, header, payload):
        super(ConnectionPacket, self).__init__(header, payload)

        if (self.class_, self.cmd) != (3, 0):
            raise ValueError('Attempted to create connection packet from wrong packet type')

        _, flags = struct.unpack_from("<BB", payload)
        self.new = bool(flags & (1 << 2))
        self.connected = bool(flags & (1 << 0))


class DeviceNotConfiguredError(Exception):
    pass


def _packet_length(header):
    """Find the BGAPI packet length given its header"""

    highbits = header[0] & 0b11
    lowbits = header[1]

    return (highbits << 8) | lowbits


class AsyncPacketReader:
    HEADER_LENGTH = 4

    def __init__(self, filelike, callback):
        """
        Given an underlying file like object, synchronously read from it
        in a separate thread and communicate the data back to the buffer
        one packet at a time.
        """

        self.file = filelike
        self._stop = Event()

        self._thread = Thread(target=_reader_thread,
                              args=(filelike, callback, self.HEADER_LENGTH, _packet_length, self._stop))
        self._thread.start()

    def write(self, value):
        try:
            self.file.write(value)
        except SerialException as err:
            raise DeviceNotConfiguredError("Device not configured properly") from err

    def stop(self):
        self._stop.set()

        if hasattr(self.file, 'cancel_read'):
            self.file.cancel_read()

        self._thread.join()


def _reader_thread(filelike, callback, header_length, length_function, stop):
    logger = logging.getLogger(__name__)

    while not stop.is_set():
        try:
            header = bytearray()
            while len(header) < header_length:
                chunk = bytearray(filelike.read(header_length - len(header)))
                header += chunk

                if stop.is_set():
                    break

            if stop.is_set():
                break

            remaining_length = length_function(header)

            remaining = bytearray()
            while len(remaining) < remaining_length:
                chunk = bytearray(filelike.read(remaining_length - len(remaining)))
                remaining += chunk
                if stop.is_set():
                    break

            if stop.is_set():
                break

            # We have a complete packet now, process it
            packet = BGAPIPacket(header, remaining)
            logger.log(5, "BLED112 Packet: class=%d, cmd=%d, event=%s, payload_length=%d",
                       packet.class_, packet.cmd, packet.event, len(packet.payload))
            if packet.class_ == 3 and packet.cmd == 0:
                packet = ConnectionPacket(header, remaining)

            callback(packet)
        except:
            logger.exception("Error in reader thread")
            break
