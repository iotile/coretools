from .auth_provider import AuthProvider

from iotile.core.exceptions import NotFoundError

class NullAuthProvider(AuthProvider):
    """Auth provider that use null root key, zeroes"""

    root_key = bytearray(16)

    def get_rotated_key(self, key_type, device_id, **rotation_info):

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

        reboot_key = AuthProvider.DeriveRebootKey(self.root_key, 0, counter)

        temp_key = AuthProvider.DeriveRotatedKey(reboot_key, timestamp, interval_power)
        return temp_key


    def get_serialized_key(self, key_type, device_id, **key_info):
        """Get a serialized key such for signing a streamer report.

        These keys are designed to only be used once and only provide
            access to the object of ``key_type`` with the given
            ``serial_number``.
        """
        report_id = key_info.get('report_id', None)
        sent_timestamp = key_info.get('sent_timestamp', None)

        if report_id is None or sent_timestamp is None:
            raise NotFoundError('report_id or sent_timestamp not provided in EnvAuthProvider.sign_report')

        AuthProvider.VerifyRoot(key_type)

        if key_type != AuthProvider.UserKey:
            raise NotFoundError('unsupported root key in EnvAuthProvider', root_key=key_type)

        report_key = AuthProvider.DeriveReportKey(self.root_key, report_id, sent_timestamp)

        return report_key
