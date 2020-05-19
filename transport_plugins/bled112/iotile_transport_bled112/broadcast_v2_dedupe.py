"""This module is used to identify and filter out broadcast v2 broadcasts, which leads to significant
performance increases.
"""

import time
import struct
import collections
from typing import Dict

from iotile.cloud.utilities import device_id_to_slug

def packet_is_broadcast_v2(packet: bytearray) -> bool:
    """Simple/efficient check for whether a given packet from the bled112 is an IOTile Broadcast v2 packet."""
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

class BroadcastV2DeduperCollection:
    """Main interface into the Broadcast v2 deduplication code.

    This contains a dictionary, keyed on the broadcast sender's encoded UUID, and with the values being
    a small class that stores the last received packet from that UUID and the last time the packet
    was forwarded. That class (bc_v2_deduper) will report whether the packet is new and should be allowed through.

    Args:
        pass_packets_every(float, seconds): For each encoded_uuid address, at least one packet will be allowed through
            every "pass_packets_every" seconds
    """

    MAX_DEDUPERS = 500

    def __init__(self, pass_packets_every: float = 5):
        self._pass_packets_every = pass_packets_every
        self.dedupers = collections.OrderedDict()  #type: collections.OrderedDict[bytes, BroadcastV2Deduper]

    def allow_packet(self, packet: bytearray) -> bool:
        """Run a packet through the broadcast_v2 deduper.

        Returns False if the packet should be dropped
        """

        if not packet_is_broadcast_v2(packet):
            return True

        encoded_uuid = bytes(packet[22:26])
        data = bytes(packet[22:])

        deduper = self.dedupers.get(encoded_uuid)
        if deduper is None:
            deduper = BroadcastV2Deduper(encoded_uuid, self._pass_packets_every)
            if len(self.dedupers) == self.MAX_DEDUPERS:
                self.evict_oldest_deduper()
            self.dedupers[encoded_uuid] = deduper

        return deduper.allow_packet(data)

    def evict_oldest_deduper(self):
        """Find and remove the oldest deduper

        This function will likely be called rarely, if at all
        """
        self.dedupers.popitem(last=False)

class BroadcastV2Deduper():
    """Individual deduplicator for an specific UUID."""
    def __init__(self, encoded_uuid: bytes, pass_packets_every: float = 5):
        self.encoded_uuid = encoded_uuid
        self._pass_packets_every = pass_packets_every
        self.last_allowed_packet = 0 #type: float
        self.last_data = bytes()

        self._slug = ""

    def get_slug(self):
        """For debugging, unpack the UUID into a slug so it can be printed. Only do this if needed though."""
        if self._slug:
            return self._slug

        uuid = struct.unpack("<L", self.encoded_uuid)
        self._slug = device_id_to_slug("%04X" % uuid)
        return self._slug

    def allow_packet(self, broadcast_data: bytes)-> bool:
        """Check if the packet is allowed. If so, save it and return True. Otherwise return False."""
        if (time.monotonic() > self.last_allowed_packet + self._pass_packets_every or
                self.last_data != broadcast_data):
            self.last_data = broadcast_data
            self.last_allowed_packet = time.monotonic()
            return True

        return False
        