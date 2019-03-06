from threading import Thread, Event
from queue import Queue, Empty
import logging
from serial import SerialException


class InternalTimeoutError(Exception):
    pass


class DeviceNotConfiguredError(Exception):
    pass


class AsyncPacketBuffer:
    def __init__(self, filelike, header_length, length_function):
        """
        Given an underlying file like object, synchronously read from it
        in a separate thread and communicate the data back to the buffer
        one packet at a time.
        """

        self.queue = Queue()
        self.file = filelike
        self._stop = Event()

        self._thread = Thread(target=ReaderThread, args=(filelike, self.queue, header_length, length_function, self._stop))
        self._thread.start()

    def write(self, value):
        try:
            self.file.write(value)
        except SerialException:
            raise DeviceNotConfiguredError("Device not configured properly")

    def stop(self):
        self._stop.set()
        self._thread.join()

    def has_packet(self):
        """return True if there is a packet waiting in the queue."""

        return not self.queue.empty()

    def read_packet(self, timeout=3.0):
        """read one packet, timeout if one packet is not available in the timeout period"""

        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            raise InternalTimeoutError("Timeout waiting for packet in AsyncPacketBuffer")


def ReaderThread(filelike, read_queue, header_length, length_function, stop):
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
            packet = header + remaining
            read_queue.put(packet)
        except:
            logger.exception("Error in reader thread")
