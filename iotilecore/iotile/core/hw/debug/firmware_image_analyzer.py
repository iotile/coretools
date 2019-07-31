from iotile.core.utilities.intelhex import IntelHex
from iotile.core.exceptions import *
from tempfile import NamedTemporaryFile
import os
import subprocess
import struct

class FirmwareImageAnalyzer:
    """A firmware image analyzer using IntelHex"""

    KNOWN_FIRMWARE_NAMES = ['boot52', 'NRF52 ', 'firmPP', 'UART  ', 'firmFF']
    SIZE_OF_CDBAPPINFO = 32
    MAGIC_NUMBER_BYTE_OFFSET = 24

    def __init__(self, firmware, magic_number=0xBAADDAAD):
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

        self.cdb_app_info = None
        self.min_addr = self._hex_image.minaddr()
        self.max_addr = self._hex_image.maxaddr()
        self.num_addresses = len(self._hex_image.addresses())
        self.segments = self._hex_image.segments()
        self.memory_size = self._hex_image.get_memory_size()
        self.magic_number = magic_number

    def set_firmware_magic_number(self, magic_number):
        """Sets the magic number to search a CDB app info block by
        """
        if isinstance(magic_number, int):
            self.magic_number = magic_number
        else:
            raise ArgumentError("You must pass in a valid magic number")

    def get_firmware_hardware_type(self):
        """Returns hardware type specified in cdb app info
        """
        if self.cdb_app_info is None:
            self.get_cdb_app_info()

        return self.cdb_app_info['hardware_type']

    def get_firmware_api_version(self):
        """Returns firmware api version specified in cdb app info
        """
        if self.cdb_app_info is None:
            self.get_cdb_app_info()

        return (self.cdb_app_info['api_major_version'],
                self.cdb_app_info['api_minor_version'])

    def get_firmware_name(self):
        """Returns firmware name specified in cdb app info
        """
        if self.cdb_app_info is None:
            self.get_cdb_app_info()

        return self.cdb_app_info['name'].decode("utf-8")

    def get_firmware_version(self):
        """Returns firmware module version specified in cdb app info
        """
        if self.cdb_app_info is None:
            self.get_cdb_app_info()

        return (self.cdb_app_info['module_major_version'],
                self.cdb_app_info['module_minor_version'],
                self.cdb_app_info['module_patch_version'])

    def get_cdb_app_info(self):
        """Gets the string of bytes of the CDB app info
        """
        cdb_app_info_bytes = self._hex_image.gets(self.max_addr - (FirmwareImageAnalyzer.SIZE_OF_CDBAPPINFO - 1), \
                FirmwareImageAnalyzer.SIZE_OF_CDBAPPINFO)
        if self._check_cdb_app_info(cdb_app_info_bytes):
            self.cdb_app_info = self._format_cdb_app_info(cdb_app_info_bytes)
            return self.cdb_app_info

        addresses = self._hex_image.addresses()
        for address_index in range(0, self.num_addresses - 4):
            search_bytes = self._hex_image.gets(addresses[address_index], 4)
            search, = struct.unpack("<L", search_bytes)
            if search == self.magic_number:
                cdb_app_info_bytes = self._hex_image.gets(addresses[address_index - FirmwareImageAnalyzer.MAGIC_NUMBER_BYTE_OFFSET], \
                    FirmwareImageAnalyzer.SIZE_OF_CDBAPPINFO)
                if self._check_cdb_app_info(cdb_app_info_bytes):
                    self.cdb_app_info = self._format_cdb_app_info(cdb_app_info_bytes)
                    return self.cdb_app_info
                

    def _check_cdb_app_info(self, cdb_app_info_bytes):
        """Helper function to check the byte string if it is a valid CDB app info
        """
        _hardware_type, _api_major_version, _api_minor_version, name, _module_major_version, \
            _module_minor_version, _module_patch_version, _num_slave_commands, _num_required_configs, \
            _num_total_configs, _reserved, _p_config_variables, _p_slave_handlers, magic_number, \
            _firmware_checksum = struct.unpack("<BBB6sBBBBBBBLLLL", cdb_app_info_bytes)
        cdb_app_info = self._format_cdb_app_info(cdb_app_info_bytes)

        try:
            name = cdb_app_info['name'].decode("utf-8")
        except:
            return False

        if name in FirmwareImageAnalyzer.KNOWN_FIRMWARE_NAMES \
            and cdb_app_info['magic_number'] == self.magic_number:
            return True

        return False

    def _format_cdb_app_info(self, cdb_app_info_bytes):
        """Helper function to format the cdb_app_info byte string to dict
        """
        hardware_type, api_major_version, api_minor_version, name, module_major_version, \
            module_minor_version, module_patch_version, num_slave_commands, num_required_configs, \
            num_total_configs, reserved, p_config_variables, p_slave_handlers, magic_number, \
            firmware_checksum = struct.unpack("<BBB6sBBBBBBBLLLL", cdb_app_info_bytes)

        cdb_app_info = dict()
        cdb_app_info['hardware_type'] = hardware_type
        cdb_app_info['api_major_version'] = api_major_version
        cdb_app_info['api_minor_version'] = api_minor_version
        cdb_app_info['name'] = name
        cdb_app_info['module_major_version'] = module_major_version
        cdb_app_info['module_minor_version'] = module_minor_version
        cdb_app_info['module_patch_version'] = module_patch_version
        cdb_app_info['num_slave_commands'] = num_slave_commands
        cdb_app_info['num_required_configs'] = num_required_configs
        cdb_app_info['num_total_configs'] = num_total_configs
        cdb_app_info['reserved'] = reserved
        cdb_app_info['p_config_variables'] = p_config_variables
        cdb_app_info['p_slave_handlers'] = p_slave_handlers
        cdb_app_info['magic_number'] = magic_number
        cdb_app_info['firmware_checksum'] = firmware_checksum

        return cdb_app_info
