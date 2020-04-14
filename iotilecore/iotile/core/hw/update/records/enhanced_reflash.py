"""An enhanced reflash controller record."""

import struct
from iotile.core.exceptions import ArgumentError
from ..record import UpdateRecord, MatchQuality


class EnhancedReflashControllerRecord(UpdateRecord):
    """Enhanced Reflash for an IOTile controller.

        This record is based off the ReflashControllerRecord. This "enhanced"
        version contains additional parameters to allow for a more advanced
        way to reflash an IOTile device. The normal ReflashControllerRecord
        is simple and flashes binary data to flash offset. This record has
        options to allow for settings and flags to allow for future expansion.

        Args:
            raw_data (bytearray): The raw binary firmware data that we should
                program.
            base_address (int): The absolute memory offset at which raw_data 
                starts.
            image_type (int): *The type of firmware image
            flags (int): Specific flags to process
            compression_type (int): *How the appended image data is compressed
            compression_settings_length (int): *Length of compression settings
            compression_settings (bytearray): *Settings for compression
            preinstall_checks (bytearray): *Options to check during install 

        Note:
            The arguments marked with an asterisk(*) means that those features
            have not been implemented yet. This is just allowing for future
            expansion.
    """

    RecordType = 6
    RecordHeaderLength = 96

    def __init__(self, raw_data, base_address, image_type=0, flags=0,
                 compression_type=0, compression_settings_length=0,
                 compression_settings=0, preinstall_checks= 0):
        self.raw_data = raw_data
        self.base_address = base_address
        self.image_type = image_type
        self.flags = flags
        self.compression_type = compression_type
        self.compression_settings_length = compression_settings_length
        self.compression_settings = self.compression_settings
        self.preinstall_checks = self.preinstall_checks

    def encode_contents(self):
        """Encode the contents of the enhanced reflash record.

        Returns:
            bytearray: The encoded contents
        """

        header = struct.pack("<LLLBBBB16s64s", self.base_address,
                             len(self.raw_data), len(self.raw_data),
                             self.image_type, self.flags, self.compression_type,
                             self.compression_settings_length,
                             self.compression_settings, self.preinstall_checks)

        return bytearray(header) + self.raw_data