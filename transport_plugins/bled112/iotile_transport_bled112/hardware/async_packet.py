from threading import Thread, Event
import struct
import logging
from serial import SerialException
from . import packets

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
            packet = packets.create_packet(header, remaining)
            logger.log(5, "BLED112 Packet: class=%d, cmd=%d, event=%s, payload_length=%d",
                       packet.class_, packet.cmd, packet.event, len(packet.payload))

            callback(packet)
        except Exception as err:
            logger.debug("Error in reader thread, exiting", exc_info=True)
            callback(packets.HardwareFailurePacket(err))
            return
