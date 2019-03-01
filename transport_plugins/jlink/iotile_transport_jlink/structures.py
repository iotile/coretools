"""Helper routines for processing data received from an IOTile device."""


import struct
from iotile.core.exceptions import HardwareError


class ControlStructure:
    """A shared memory control structure allowing bidirectional communication with an IOTile device."""

    # The control structure in RAM is 16 bytes long
    # 4 bytes of 0xAA
    # The ASCII characters IOTileCN
    # 4 bytes of 0xBB
    CONTROL_MAGIC_1 = 0xAAAAAAAA
    CONTROL_MAGIC_2 = 0x69544f49
    CONTROL_MAGIC_3 = 0x4e43656c
    CONTROL_MAGIC_4 = 0xBBBBBBBB

    KNOWN_VERSIONS = frozenset([1])

    # The offset from the start of our debug info to where the tb_fabric_tls_t structure is located
    RPC_TLS_OFFSET = 28

    def __init__(self, address, raw_data):
        self.base_address = address

        magic1, magic2, magic3, magic4, version, flags, length = struct.unpack_from("<LLLLBBH", raw_data)

        if magic1 != self.CONTROL_MAGIC_1 or magic2 != self.CONTROL_MAGIC_2 or magic3 != self.CONTROL_MAGIC_3 or magic4 != self.CONTROL_MAGIC_4:
            raise HardwareError("Invalid control structure with an incorrect magic number", base_address=address)

        self.version = version
        self.flags = flags

        if len(raw_data) < length:
            raise HardwareError("Control structure raw data is too short for encoded length", encoded_length=length, received_length=len(raw_data))
        elif len(raw_data) > length:
            raw_data = raw_data[:length]

        if version not in self.KNOWN_VERSIONS:
            raise HardwareError("Unknown version embedded in control structure", version=version, known_versions=self.KNOWN_VERSIONS)

        self._parse_control_structure(raw_data)

    def _parse_control_structure(self, data):
        # Skip the header information
        data = data[20:]

        self.uuid, = struct.unpack_from("<L", data)

    def poll_info(self):
        """Return the address and mask to determine if an RPC is finished."""

        return self.base_address + self.RPC_TLS_OFFSET + 11, (1 << 2) | (1 << 3)

    def response_info(self):
        """Return the address and read size of the RPC resonse storage area."""

        return self.base_address + self.RPC_TLS_OFFSET + 8, 32

    def format_rpc(self, address, rpc_id, payload):
        """Create a formated word list that encodes this rpc."""

        addr_word = (rpc_id | (address << 16) | ((1 << 1) << 24))

        send_length = len(payload)
        if len(payload) < 20:
            payload = payload + b'\0'*(20 - len(payload))

        payload_words = struct.unpack("<5L", payload)

        return self.base_address + self.RPC_TLS_OFFSET + 8, ([addr_word, send_length, 0] + [x for x in payload_words])

    def format_response(self, response_data):
        """Format an RPC response."""

        _addr, length = self.response_info()
        if len(response_data) != length:
            raise HardwareError("Invalid response read length, should be the same as what response_info() returns", expected=length, actual=len(response_data))

        resp, flags, received_length, payload = struct.unpack("<HxBL4x20s", response_data)
        resp = resp & 0xFF
        if flags & (1 << 3):
            raise HardwareError("Could not grab external gate")

        if received_length > 20:
            raise HardwareError("Invalid received payload length > 20 bytes", received_length=received_length)

        payload = payload[:received_length]

        return {
            'status': resp,
            'payload': payload
        }
