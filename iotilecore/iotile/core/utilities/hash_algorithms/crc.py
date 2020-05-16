import crcmod
from iotile.core.exceptions import ArgumentError

def calculate_crc(crc_type, data):
    """Uses crc to calculate a checksum"""

    if crc_type == 0x104C11DB7:
        crc_func = crcmod.mkCrcFun(crc_type, initCrc=0xFFFFFFFF,
                                             rev=False, xorOut=0)
        checksum = crc_func(data) & 0xFFFFFFFF

        return hex(checksum)

    raise ArgumentError("Unknown/Unimplemented crc algorithm")
