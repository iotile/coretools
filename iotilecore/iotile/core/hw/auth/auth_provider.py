""" Interface that provides access to keys"""

import hashlib
import struct
import hmac
from Crypto.Cipher import AES
from iotile.core.exceptions import NotFoundError

class AuthProvider:
    """ Base calls for all objects that provide a way to obtaine a key
    """

    ReportKeyMagic = 0x00000002

    NoKey = 0
    UserKey = 1
    DeviceKey = 2

    KnownKeyRoots = {
        NoKey: 'no_key',
        UserKey: 'user_key',
        DeviceKey: 'device_key'
    }

    def __init__(self, args=None):
        if args is None:
            args = {}

        self.args = args

    @classmethod
    def VerifyRoot(cls, root_key_type):
        """Verify that the root key type is known to us.

        Raises:
            NotFoundError: If the key type is not known.
        """

        if root_key_type in cls.KnownKeyRoots:
            return

        raise NotFoundError("Unknown key type", key=root_key_type)


    @classmethod
    def DeriveReportKey(cls, root_key, report_id, sent_timestamp):
        """Derive a standard one time use report signing key.

        The standard method is HMAC-SHA256(root_key, MAGIC_NUMBER || report_id || sent_timestamp)
        where MAGIC_NUMBER is 0x00000002 and all integers are in little endian.
        """

        signed_data = struct.pack("<LLL", AuthProvider.ReportKeyMagic, report_id, sent_timestamp)

        hmac_calc = hmac.new(root_key, signed_data, hashlib.sha256)
        return bytearray(hmac_calc.digest())


    @classmethod
    def DeriveRebootKey(cls, root_key, key_purpose, reboot_counter):
        """ Derive a key generated on reboot

        HMAC SHA-256-128(Root Key, key purpose (uint32_t) || reboot counter (uint32_t))
        """
        signed_data = struct.pack("<LL", key_purpose, reboot_counter)

        hmac_calc = hmac.new(root_key, signed_data, hashlib.sha256)
        return bytearray(hmac_calc.digest()[:16])


    @classmethod
    def DeriveRotatedKey(cls, reboot_key, current_timestamp, rotation_interval_power):
        """ Derive an ephemeral key every 2^X seconds,

        AES-128-ECB(Reboot Key, current_timestamp with low X bits masked to 0)
        """
        timestamp = current_timestamp & (~(2 ** rotation_interval_power - 1))
        cipher = AES.new(reboot_key, AES.MODE_ECB)
        msg = struct.pack("<LLLL", timestamp, 0, 0, 0)

        return cipher.encrypt(msg)


    def get_serialized_key(self, key_type, device_id, **key_info):
        """Get a serialized key such for signing a streamer report.

        These keys are designed to only be used once and only provide
            access to the object of ``key_type`` with the given
            ``serial_number``.
        """
        raise NotImplementedError()


    def get_rotated_key(self, key_type, device_id, **rotation_info):
        """Get a key that is only valid for a limit period of time.

        ``rotation_info`` should be a KeyRotationInfo object that
            describes the conditions when the key is rotated.  For example,
            for a broadcast report key it may be the reboot counter of the
            device, the current uptime and the rotation interval of the key
        """
        raise NotImplementedError()


    def get_root_key(self, key_type, device_id):
        """Get the actual root key of a given type for a device.

        Few AuthProvider classes should actually implement this method
        since it's safer to only handle derived keys that give specific
        abilities.  For AuthProviders that have access to the root key
            though, the other methods can be provided via a mixin from this
            root method.
        """

        raise NotImplementedError()


    def get_device_access_key(self, key_type, device_id, scope):
        """Future method for scoped access tokens to device."""

        raise NotImplementedError()
