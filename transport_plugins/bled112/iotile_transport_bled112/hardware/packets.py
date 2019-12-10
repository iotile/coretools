"""Internal packet classes for the various packets we can receive from a bled112."""

import struct

class BGAPIPacket:
    __slots__ = ['class_', 'cmd', 'event', 'payload', 'conn', 'type']

    _CONN_EVENTS = frozenset([
        (4, 1), (4, 2), (4, 4), (4, 5), (3, 0), (3, 4)
    ])

    def __init__(self, header, payload):
        flags, class_, command = struct.unpack("<BxBB", header)

        self.class_ = class_
        self.event = flags == 0x80
        self.cmd = command
        self.payload = payload
        self.type = (class_, command)

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


class DisconnectionPacket(BGAPIPacket):
    """Special packet for disconnection events."""

    __slots__ = ['reason']

    def __init__(self, header, payload):
        super(DisconnectionPacket, self).__init__(header, payload)

        if (self.class_, self.cmd) != (3, 4):
            raise ValueError('Attempted to create disconnection packet from wrong packet type')

        _, reason = struct.unpack_from("<BH", payload)
        self.reason = reason


class HardwareFailurePacket:
    """Special packet to indicate a hardware failure."""

    def __init__(self, exception):
        self.class_ = 0xff
        self.cmd = 0xff
        self.exception = exception


_PACKET_TYPES = {
    (3, 0): ConnectionPacket,
    (3, 4): DisconnectionPacket
}

def create_packet(header: bytes, payload: bytes):
    """Unserialize a binary bgapi packet."""

    packet_type = (header[2], header[3])

    factory = _PACKET_TYPES.get(packet_type, BGAPIPacket)
    return factory(header, payload)
