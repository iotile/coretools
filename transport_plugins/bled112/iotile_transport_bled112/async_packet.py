from serial import SerialException
from threading import Thread, Event
from queue import Queue, Empty
import logging

from .broadcast_v2_dedupe import BroadcastV2DeduperCollection, packet_is_broadcast_v2


class InternalTimeoutError(Exception):
    pass


class DeviceNotConfiguredError(Exception):
    pass


class AsyncPacketBuffer:
    def __init__(self, filelike, header_length, length_function, config=None):
        """
        Given an underlying file like object, synchronously read from it
        in a separate thread and communicate the data back to the buffer
        one packet at a time.
        """

        self.queue = Queue()
        self.file = filelike
        self._stop = Event()

        dedupe = False
        dedupe_timeout = 0
        if config:
            dedupe = config.get('bled112:deduplicate-broadcast-v2')
            dedupe_timeout = config.get('bled112:dedupe-bc-v2-timeout')
        self._thread = Thread(target=reader_thread,
                              args=(filelike, self.queue, header_length, length_function, self._stop), 
                              kwargs={'dedupe':dedupe, 'dedupe_timeout':dedupe_timeout})
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


def ReaderThread(filelike, read_queue, header_length, length_function, stop, dedupe=False, dedupe_timeout=5):
    logger = logging.getLogger(__name__)
    broadcast_v2_dedupers = None
    read_buffer = bytearray()

    if dedupe:
        broadcast_v2_dedupers = BroadcastV2DeduperCollection(dedupe_timeout)

    while not stop.is_set():
        try:
            # The bled112 will read EOF when there is no more data, so it's safe to read a large amount
            read_buffer += bytearray(filelike.read(1024))

            while not stop.is_set() and len(read_buffer) >= header_length:
                next_packet_len = header_length + length_function(read_buffer[:header_length])

                if len(read_buffer) < next_packet_len:
                    # Still waiting to read this packet
                    break

                # Process the packet and remove it from the read buffer
                packet = read_buffer[:next_packet_len]
                del read_buffer[:next_packet_len]

                if broadcast_v2_dedupers:
                    if not broadcast_v2_dedupers.allow_packet(packet):
                        continue

                if stop.is_set():
                    break

                read_queue.put(packet)

        except:
            logger.exception("Error in reader thread")
            break
