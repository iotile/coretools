from iotile.core.utilities.intelhex import IntelHex
from iotile.core.exceptions import *
from tempfile import NamedTemporaryFile
import os
import subprocess

class FirmwareImageAnalyzer:
    """A firmware image analyzer using IntelHex"""
    def __init__(self, firmware):
        if not firmware.endswith(".elf") and not firmware.endswith(".hex"):
            raise ArgumentError("You must pass an ARM firmware image in elf/hex format", path=firmware)

        tmpf = NamedTemporaryFile(delete=False)
        tmpf.close()

        tmp = tmpf.name

        try:
            if firmware.endswith(".elf"):
                err = subprocess.call(['arm-none-eabi-objcopy', '-O', 'ihex', firmware, tmp])
                if err != 0:
                    raise ExternalError("Cannot convert elf to binary file", error_code=err)
            
                hex_image = IntelHex(tmp)
            else:
                hex_image = IntelHex(firmware)

            self._hex_image = hex_image
        finally:
            os.remove(tmp)

        self.min_addr = self._hex_image.minaddr()
        self.max_addr = self._hex_image.maxaddr()
        