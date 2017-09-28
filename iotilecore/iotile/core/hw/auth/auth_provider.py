"""Auth providers are classes that can encrypt, decrypt, sign or verify data from IOTile devics

All auth providers must inherit from the AuthProvider class defined in this file and override the
methods that it provides with their own implementations.
"""

#pylint:disable=C0103

import pkg_resources
import hashlib
import struct
import hmac
from iotile.core.exceptions import NotFoundError, ArgumentError


class AuthProvider(object):
    """Base class for all objects that provide a way to authenticate or protect data.

    There are three kinds of things that are encrypted or signed in an IOTileDevice:

    1. Reports: Reports are signed using a unique per report key derived from a root
        key embedded on the device that guarantees its authenticity.
    2. RPCs: RPCs are signed using a per-session key derived from a token generated
        from a root key embedded on the device.
    3. Scripts: Scripts are signed using a unique key derived from a root key embedded
        on the device that guarantees its authenticity.

    Args:
        args (dict): An optional dictionary of AuthProvider specific config information
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
    def FindByName(cls, name):
        """Find a specific installed auth provider by name."""

        for entry in pkg_resources.iter_entry_points('iotile.auth_provider'):
            if entry.name == name:
                return entry.load()

    @classmethod
    def VerifyRoot(cls, root):
        """Verify that the root key type is known to us.

        Raises:
            NotFoundError: If the key type is not known.
        """

        if root in cls.KnownKeyRoots:
            return

        raise NotFoundError("Unknown key type", key=root)

    @classmethod
    def DeriveReportKey(cls, root_key, report_id, sent_timestamp):
        """Derive a standard one time use report signing key.

        The standard method is HMAC-SHA256(root_key, MAGIC_NUMBER || report_id || sent_timestamp)
        where MAGIC_NUMBER is 0x00000002 and all integers are in little endian.
        """

        signed_data = struct.pack("<LLL", AuthProvider.ReportKeyMagic, report_id, sent_timestamp)

        hmac_calc = hmac.new(root_key, signed_data, hashlib.sha256)
        return bytearray(hmac_calc.digest())

    def encrypt_report(self, device_id, root, data, **kwargs):
        """Encrypt a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should encrypt.
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The encrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        raise NotFoundError("encrypt_report method is not implemented")

    def decrypt_report(self, device_id, root, data, **kwargs):
        """Encrypt a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should decrypt
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The encrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to decrypt the data.
        """

        raise NotFoundError("decrypt_report method is not implemented")

    def sign_report(self, device_id, root, data, **kwargs):
        """Sign a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should sign
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The signature and any associated metadata about the signature.
                The signature itself must always be a bytearray stored under the
                'signature' key, however additional keys may be present depending
                on the signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to sign the data.
        """

        raise NotFoundError("sign_report method is not implemented")

    def verify_report(self, device_id, root, data, signature, **kwargs):
        """Verify a buffer of report data on behalf of a device.

        Args:
            device_id (int): The id of the device that we should encrypt for
            root (int): The root key type that should be used to generate the report
            data (bytearray): The data that we should verify
            signature (bytearray): The signature attached to data that we should verify
            **kwargs: There are additional specific keyword args that are required
                depending on the root key used.  Typically, you must specify
                - report_id (int): The report id
                - sent_timestamp (int): The sent timestamp of the report

                These two bits of information are used to construct the per report
                signing and encryption key from the specific root key type.

        Returns:
            dict: The result of the verification process must always be a bool under the
                'verified' key, however additional keys may be present depending on the
                signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to verify the data due to
                an error.  If the data is simply not valid, then the function returns
                normally.
        """

        raise NotFoundError("verify method is not implemented")
