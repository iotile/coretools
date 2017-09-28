"""A Basic authentication provider that can just sign with SHA256 hash."""

import hashlib
import hmac
from iotile.core.exceptions import NotFoundError
from .auth_provider import AuthProvider


class BasicAuthProvider(AuthProvider):
    """Basic default authentication provider that can only calculate sha256 hashes
    """

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

        AuthProvider.VerifyRoot(root)

        if root != AuthProvider.NoKey:
            raise NotFoundError('unsupported root key in BasicAuthProvider', root_key=root)

        result = bytearray(hashlib.sha256(data).digest())
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

        AuthProvider.VerifyRoot(root)

        if root != AuthProvider.NoKey:
            raise NotFoundError('unsupported root key in BasicAuthProvider', root_key=root)


        result = bytearray(hashlib.sha256(data).digest())

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
