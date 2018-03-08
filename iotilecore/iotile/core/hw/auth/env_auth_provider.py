"""An auth provider that can sign and verify with user keys stored in environment variables."""

import hashlib
import hmac
import binascii
import os
from iotile.core.exceptions import NotFoundError
from .auth_provider import AuthProvider


class EnvAuthProvider(AuthProvider):
    """Authentication provider that can sign and verify using user keys

    Keys must be defined in environment variables with the naming scheme:
    USER_KEY_ABCDEFGH where ABCDEFGH is the device uuid in hex prepended with 0s
    and expressed in capital letters.  So the device with UUID 0xab would look
    for the environment variable USER_KEY_000000AB.

    The key must be a 64 character hex string that is decoded to create a 32 byte key.
    """

    @classmethod
    def _get_key(cls, device_id):
        """Attempt to get a user key from an environment variable
        """

        var_name = "USER_KEY_{0:08X}".format(device_id)

        if var_name not in os.environ:
            raise NotFoundError("No user key could be found for devices", device_id=device_id, expected_variable_name=var_name)

        key_var = os.environ[var_name]
        if len(key_var) != 64:
            raise NotFoundError("User key in variable is not the correct length, should be 64 hex characters", device_id=device_id, key_value=key_var)

        try:
            key = binascii.unhexlify(key_var)
        except ValueError:
            raise NotFoundError("User key in variable could not be decoded from hex", device_id=device_id, key_value=key_var)

        if len(key) != 32:
            raise NotFoundError("User key in variable is not the correct length, should be 64 hex characters", device_id=device_id, key_value=key_var)

        return key

    @classmethod
    def _verify_derive_key(cls, device_id, root, **kwargs):
        report_id = kwargs.get('report_id', None)
        sent_timestamp = kwargs.get('sent_timestamp', None)

        if report_id is None or sent_timestamp is None:
            raise NotFoundError('report_id or sent_timestamp not provided in EnvAuthProvider.sign_report')

        AuthProvider.VerifyRoot(root)

        if root != AuthProvider.UserKey:
            raise NotFoundError('unsupported root key in EnvAuthProvider', root_key=root)

        root_key = cls._get_key(device_id)
        report_key = AuthProvider.DeriveReportKey(root_key, report_id, sent_timestamp)

        return report_key

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

        report_key = self._verify_derive_key(device_id, root, **kwargs)

        #We sign the SHA256 hash of the message
        message_hash = hashlib.sha256(data).digest()
        hmac_calc = hmac.new(report_key, message_hash, hashlib.sha256)
        result = bytearray(hmac_calc.digest())

        return {'signature': result, 'root_key': root}

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

        report_key = self._verify_derive_key(device_id, root, **kwargs)

        message_hash = hashlib.sha256(data).digest()
        hmac_calc = hmac.new(report_key, message_hash, hashlib.sha256)
        result = bytearray(hmac_calc.digest())

        if len(signature) == 0:
            verified = False
        elif len(signature) > len(result):
            verified = False
        elif len(signature) < len(result):
            trunc_result = result[:len(signature)]
            verified = hmac.compare_digest(signature, trunc_result)
        else:
            verified = hmac.compare_digest(signature, result)

        return {'verified': verified, 'bit_length': 8*len(signature)}

    def decrypt_report(self, device_id, root, data, **kwargs):
        """Decrypt a buffer of report data on behalf of a device.

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
            dict: The decrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to decrypt the data.
        """

        report_key = self._verify_derive_key(device_id, root, **kwargs)

        try:
            from Crypto.Cipher import AES
            import Crypto.Util.Counter
        except ImportError:
            raise NotFoundError

        ctr = Crypto.Util.Counter.new(128)

        # We use AES-128 for encryption
        encryptor = AES.new(bytes(report_key[:16]), AES.MODE_CTR, counter=ctr)

        decrypted = encryptor.decrypt(bytes(data))
        return {'data': decrypted}

    def encrypt_report(self, device_id, root, data, **kwargs):
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

        report_key = self._verify_derive_key(device_id, root, **kwargs)

        try:
            from Crypto.Cipher import AES
            import Crypto.Util.Counter
        except ImportError:
            raise NotFoundError

        # We use AES-128 for encryption
        ctr = Crypto.Util.Counter.new(128)
        encryptor = AES.new(bytes(report_key[:16]), AES.MODE_CTR, counter=ctr)

        encrypted = encryptor.encrypt(bytes(data))
        return {'data': encrypted}
