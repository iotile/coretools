""" Interface that provides access to keys"""

import hashlib
import struct
import hmac
from iotile.core.exceptions import NotFoundError

class AuthProvider:
    """Base class for all objects that provide a way to obtain a key

    Args:
        args (dict): An optional dictionary of AuthProvider specific config information
            field "supported_keys" specify wich keys the AuthProvider supports
    """

    ReportKeyMagic = 0x00000002

    NoKey = 0
    NullKey = 1
    UserKey = 2
    DeviceKey = 3
    PasswordBasedKey = 4

    KnownKeyRoots = {
        NoKey: 'no_key',
        NullKey: 'null_key',
        UserKey: 'user_key',
        DeviceKey: 'device_key',
        PasswordBasedKey: 'pasword_based_userkey'
    }

    def __init__(self, args=None):
        if args is None:
            args = {}

        self.args = args
        self.supported_keys = self.args.get("supported_keys", [])

    def verify_key(self, root_key_type):
        """Verify that the root key type is known to us.

        Args:
            root_key_type: requested key type

        Raises:
            NotFoundError: If the key type is not known.
        """

        if root_key_type not in self.KnownKeyRoots:
            raise NotFoundError("Unknown key type", key=root_key_type)

        if root_key_type not in self.supported_keys:
            raise NotFoundError("Not supported key type", key=root_key_type)

    @classmethod
    def DeriveRebootKeyFromPassword(cls, password):
        """Derive the root key from the user password
        TODO hashlib.pbkdf2_hmac arguments needs to be revised,
            current values are not proved to be secure

        Args:
            password (str): user password

        Returns:
            bytes: derived key
        """
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), b'salt', 100000)

    @classmethod
    def DeriveReportKey(cls, root_key, report_id, sent_timestamp):
        """Derive a standard one time use report signing key.

        The standard method is HMAC-SHA256(root_key, MAGIC_NUMBER || report_id || sent_timestamp)
        where MAGIC_NUMBER is 0x00000002 and all integers are in little endian.

        Args:
            root_key (bytearray): 16 bytes with the key
            report_id (int): id in report
            sent_timestamp (int): timestamp in report

        Returns:
            bytearray: 32 bytes containing digest of id and timestamp
        """

        signed_data = struct.pack("<LLL", AuthProvider.ReportKeyMagic, report_id, sent_timestamp)

        hmac_calc = hmac.new(root_key, signed_data, hashlib.sha256)
        return bytearray(hmac_calc.digest())


    @classmethod
    def DeriveRebootKey(cls, root_key, key_purpose, reboot_counter):
        """Derive a key generated on reboot

        HMAC SHA-256-128(Root Key, key purpose (uint32_t) || reboot counter (uint32_t))

        Args:
            root_key (bytearray): 16 bytes key
            key_purpose (int): value to differentiate different keys,
                for example with different permissions. Not used at the moment
            reboot_counter (int): received in ble adv packet

        Returns:
            bytearray: 16 bytes containing digest of key_purpose and reboot_counter
        """
        signed_data = struct.pack("<LL", key_purpose, reboot_counter)

        hmac_calc = hmac.new(root_key, signed_data, hashlib.sha256)
        return bytearray(hmac_calc.digest()[:16])


    @classmethod
    def DeriveRotatedKey(cls, reboot_key, current_timestamp, rotation_interval_power):
        """Derive an ephemeral key every 2^rotation_interval_power seconds,
        The same key will be return if timeout of rotation is not elapsed

        AES-128-ECB(Reboot Key, current_timestamp with low X bits masked to 0)

        Args:
            reboot_key (bytearray): 16 bytes key
            current_timestamp (int): current time
            rotation_interval_power (int): X in 2^X

        Returns:
            bytearray: the rotated key
        """
        timestamp = current_timestamp & (~(2 ** rotation_interval_power - 1))

        try:
            from Crypto.Cipher import AES
        except ImportError as error:
            raise NotFoundError("Cryptographic library is not available") from error

        cipher = AES.new(reboot_key, AES.MODE_ECB)
        msg = struct.pack("<LLLL", timestamp, 0, 0, 0)

        return cipher.encrypt(msg)


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
        raise NotImplementedError()


    def get_root_key(self, key_type, device_id):
        """Get the actual root key of a given type for a device.

        Few AuthProvider classes should actually implement this method
        since it's safer to only handle derived keys that give specific
        abilities.  For AuthProviders that have access to the root key
            though, the other methods can be provided via a mixin from this
            root method.

        Args:
            key_type (int): no key, user key or device key
            device_id (int): UUID of the device

        Returns:
            bytearray: the root key
        """

        raise NotImplementedError()


    def get_device_access_key(self, key_type, device_id, scope):
        """Future method for scoped access tokens to device.

        Args:
            key_type (int): no key, user key or device key
            device_id (int): UUID of the device
            scope (int): permissions that will be granted with this key

        Returns:
            bytearray: the key

        """
        raise NotImplementedError()
