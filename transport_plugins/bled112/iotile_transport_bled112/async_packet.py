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

#80 2a 06 00 ca 00 00 90 29 81
#25 cb 01 ff 1f 02 01 06 1b 16
#dd fd 00 90 00 00 00 00 00 00 
#23 16 00 00 a0 01 40 10 00 00
#00 00 00 00 00 00  rssi: -54, type: 0, sender: 0090298125cb
def packet_is_broadcast_v2(packet):
    #Broadcast packets consist of 32 bytes for data, 10 for BLE packet header and 4 for bled112 bgapi header
    if len(packet) != 46:
        return False
    #This identifies the bgapi packet as an event
    if not (packet[0] == 0x80 and packet[2] == 6 and packet[3] == 0):
        return False
    #This identifies the event as a broadcast v2 packet
    if not (packet[18] == 0x1b and packet[19] == 0x16 and packet[20] == 0xdd and packet[21] == 0xfd):
        return False
    return True

def packet_is_dupe(packet, dedupe_dict):
    mac = tuple(packet[6:11])
    data = packet[22:]

    #print(f"Parsing from {mac}: {data}")
    if dedupe_dict.get(mac) == data:
        #print(f"Dropping from {mac}: {data}")
        return True
    #print(f"Not a dupe    {mac}: {data}")
    dedupe_dict[mac] = data
    return False


def ReaderThread(filelike, read_queue, header_length, length_function, stop):
    logger = logging.getLogger(__name__)
    dedupe_dict = {}

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
            #qsize = read_queue.qsize()
            #qsize_limit = 50
            #if qsize % qsize_limit == qsize_limit -1:
                #logger.error("queue is %d", qsize)
                #logger.error("%d", len(packet))

            #if qsize > qsize_limit and packet_is_broadcast_v2(packet):
            if packet_is_broadcast_v2(packet):
                #if read_queue.qsize() > 25:
                if packet_is_dupe(packet, dedupe_dict):
                    #print("drop")
                    continue

                #print(packet.hex())

            read_queue.put(packet)
        except:
            logger.exception("Error in reader thread")
            break
