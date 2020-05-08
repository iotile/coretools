from serial import SerialException
from threading import Thread, Event
from queue import Queue, Empty
import logging

from .reader_stats import reader_stats
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
        logger = logging.getLogger(__name__)

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

STATS = False

def reader_thread(filelike, read_queue, header_length, length_function, stop, dedupe=False, dedupe_timeout=5):
    logger = logging.getLogger(__name__)
    broadcast_v2_dedupers = None
    read_buffer = bytearray()

    if dedupe:
        broadcast_v2_dedupers = BroadcastV2DeduperCollection(dedupe_timeout)

    if STATS:
        stats = reader_stats("All Packets", 10, 1)
        if broadcast_v2_dedupers:
            bv2stats = reader_stats("BroadcastV2", 10, 1)

    while not stop.is_set():
        try:
            # The bled112 will read EOF when there is no more data, so it's safe to read a large amount
            #logger.error("about to read, %d in buffer", len(read_buffer))
            #start = time.monotonic()
            read_buffer += bytearray(filelike.read(1024))
            #if len(read_buffer) > 1500:
                #logger.error("read, %d in buffer", len(read_buffer))
            new_seen = 0
            new_forwarded = 0
            new_bv2_seen = 0
            new_bv2_forwarded = 0

            while not stop.is_set() and len(read_buffer) >= header_length:
                next_packet_len = header_length + length_function(read_buffer[:header_length])
                #logger.error("processing packet, %d in buffer, header_len %d, next_len %d", len(read_buffer), header_length, next_packet_len)

                if len(read_buffer) < next_packet_len:
                    # Still waiting to read this packet
                    break

                # Process the packet and remove it from the read buffer
                packet = read_buffer[:next_packet_len]
                del read_buffer[:next_packet_len]
                new_seen += 1

                if broadcast_v2_dedupers and packet_is_broadcast_v2(packet):
                    new_bv2_seen += 1
                    if not broadcast_v2_dedupers.allow_packet(packet):
                        continue
                    new_bv2_forwarded += 1

                #logger.error("putting packet, %d in buffer", len(read_buffer))
                read_queue.put(packet)
                new_forwarded += 1
            # End loop
            #logger.error("Queue len %d", read_queue.qsize())
            if STATS:
                stats.add_count(new_seen, new_forwarded)
                stats.report()
                if broadcast_v2_dedupers:
                    bv2stats.add_count(new_bv2_seen, new_bv2_forwarded)
                    bv2stats.report()
        except:
            logger.exception("Error in reader thread")
            break
