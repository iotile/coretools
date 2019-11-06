
import os
import binascii
import struct
import hmac
import hashlib
from iotile.core.exceptions import NotFoundError
from .auth_provider import AuthProvider


class EnvAuthProvider(AuthProvider):
    """ Key provider implementation that search for keys in environment """

    @classmethod
    def _get_key(cls, device_id):
        """Attempt to get a user key from an environment variable
        """

        var_name = "USER_KEY_{0:08X}".format(device_id)

        if var_name not in os.environ:
            raise NotFoundError("No key could be found for devices", device_id=device_id,
                                expected_variable_name=var_name)

        key_var = os.environ[var_name]
        if len(key_var) != 64:
            raise NotFoundError("Key in variable is not the correct length, should be 64 hex characters",
                                device_id=device_id, key_value=key_var)

        try:
            key = binascii.unhexlify(key_var)
        except ValueError as exc:
            raise NotFoundError("Key in variable could not be decoded from hex", device_id=device_id,
                                key_value=key_var) from exc

        if len(key) != 32:
            raise NotFoundError("Key in variable is not the correct length, should be 64 hex characters",
                                device_id=device_id, key_value=key_var)

        return key


    def get_serialized_key(self, key_type, device_id, **key_info):
        """Get a serialized key such for signing a streamer report.

        These keys are designed to only be used once and only provide
            access to the object of key_type with the given serial_number

        Args:
            key_type (int): no key, user key or device key
            device_id (int): UUID of the device
            key_info (dict): data required for key generation,
                includes report_id and sent_timestamp

        Returns:
            bytearray: the key
        """
        report_id = key_info.get('report_id', None)
        sent_timestamp = key_info.get('sent_timestamp', None)

        if report_id is None or sent_timestamp is None:
            raise NotFoundError('report_id or sent_timestamp not provided in EnvAuthProvider.sign_report')

        AuthProvider.VerifyRoot(key_type)

        if key_type != AuthProvider.UserKey:
            raise NotFoundError('unsupported root key in EnvAuthProvider', root_key=key_type)

        root_key = self._get_key(device_id)
        report_key = AuthProvider.DeriveReportKey(root_key, report_id, sent_timestamp)

        return report_key


    def get_rotated_key(self, key_type, device_id, **rotation_info):
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
        counter = rotation_info.get("reboot_counter", None)
        interval_power = rotation_info.get("rotation_interval_power", None)
        timestamp = rotation_info.get("current_timestamp", None)

        if not counter:
            raise NotFoundError('reboot_counter is not provided in EnvAuthProvider get_rotated_key')

        if not interval_power:
            raise NotFoundError('rotation_interval_power is not provided in EnvAuthProvider get_rotated_key')

        if not timestamp:
            raise NotFoundError('timestamp is not provided in EnvAuthProvider get_rotated_key')

        AuthProvider.VerifyRoot(key_type)
        root_key = EnvAuthProvider._get_key(device_id)

        reboot_key = AuthProvider.DeriveRebootKey(root_key, 0, counter)

        temp_key = AuthProvider.DeriveRotatedKey(reboot_key, timestamp, interval_power)
        return temp_key
