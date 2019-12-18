""" Interface that provides access to keys"""

import hashlib
import struct
import hmac
from iotile.core.exceptions import NotFoundError
from .auth_provider import AuthProvider

class RootKeyAuthProvider(AuthProvider):
    """Base class for Providers that derive temporary keys from root

        Derived classes should implement get_root_key function
    """

    def get_root_key(self, key_type, device_id):
        """Get the actual root key of a given type for a device.

        Args:
            key_type (int): no key, user key or device key
            device_id (int): UUID of the device

        Returns:
            bytearray: the root key
        """
        raise NotImplementedError()

    def get_rotated_key(self, key_type, device_id, **rotation_info):
        """Get a key that is only valid for a limit period of time.

        Args:
            key_type (int): no key, user key or device key
            device_id (int): UUID of the device
            key_info (dict): data that describes the conditions when
                the key is rotated. For example, for a broadcast report key
                it may be the reboot counter of the
                device, the current uptime and the rotation interval of the key.

        Returns:
            bytearray: the rotated key
        """
        counter = rotation_info.get("reboot_counter", None)
        interval_power = rotation_info.get("rotation_interval_power", None)
        timestamp = rotation_info.get("current_timestamp", None)

        if not counter:
            raise NotFoundError('reboot_counter is not provided in EnvAuthProvider get_rotated_key')

        if not interval_power:
            raise NotFoundError('rotation_interval_power is not provided in EnvAuthProvider get_rotated_key')

        if not timestamp:
            raise NotFoundError('timestamp is not provided in EnvAuthProvider get_rotated_key')

        self.verify_key(key_type)

        root_key = self.get_root_key(key_type, device_id)
        reboot_key = self.DeriveRebootKey(root_key, 0, counter)

        temp_key = self.DeriveRotatedKey(reboot_key, timestamp, interval_power)
        return temp_key


    def get_serialized_key(self, key_type, device_id, **key_info):
        """Get a serialized key such for signing a streamer report.

        These keys are designed to only be used once and only provide
            access to the object of key_type with the given serial_number

        Args:
            key_type (int): no key, user key or device key
            device_id (int): UUID of the device
            key_info (dict): data required for key generation.
                It may be report_id and sent_timestamp

        Returns:
            bytearray: the key
        """
        report_id = key_info.get('report_id', None)
        sent_timestamp = key_info.get('sent_timestamp', None)

        if report_id is None or sent_timestamp is None:
            raise NotFoundError('report_id or sent_timestamp is not provided')

        self.verify_key(key_type)

        root_key = self.get_root_key(key_type, device_id)
        report_key = self.DeriveReportKey(root_key, report_id, sent_timestamp)

        return report_key
