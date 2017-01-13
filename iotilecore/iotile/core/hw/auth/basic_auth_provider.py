import hashlib
import hmac
import struct
from auth_provider import AuthProvider, KnownSignatureMethods
from iotile.core.exceptions import NotFoundError

class BasicAuthProvider(AuthProvider):
    """Basic default authentication provider that can only calculate sha256 hashes
    """

    def sign(self, device_id, sig_method, data):
        """Sign a buffer of data on behalf of a device

        This routine only supports hash only signatures

        Args:
            device_id (int): The id of the device that we should encrypt for
            sig_method (int): The method of encryption that we should perform
            data (bytearray): The data that we should sign

        Returns:
            dict: The signature and any associated metadata about the signature.
                The signatured itself must always be a bytearray stored under the 
                'signature' key, however additional keys may be present depending 
                on the signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to sign the data.
        """

        self._check_signature_method(sig_method)
        method_name = KnownSignatureMethods[sig_method]

        if method_name == 'hash_only_sha256':
            result = bytearray(hashlib.sha256(data).digest())
        else:
            raise NotFoundError('unsupported signature method in BasicAuthProvider', method=method_name)

        return {'signature': result, 'method': method_name}

    def verify(self, device_id, sig_method, data, signature):
        """Verify the signature attached to a buffer of data

        Args:
            device_id (int): The id of the device that we should encrypt for
            sig_method (int): The method of signing that was used
            data (bytearray): The data whose signature we should verify
            signature (bytearray): The signature attached to data

        Returns:
            dict: The result of the verification process must always be a bool under the
                'verified' key, however additional keys may be present depending on the 
                signature method used.

        Raises:
            NotFoundError: If the auth provider is not able to verify the data because the method
                is not supported.
        """

        self._check_signature_method(sig_method)
        method_name = KnownSignatureMethods[sig_method]

        if method_name == 'hash_only_sha256':
            result = bytearray(hashlib.sha256(data).digest())
        else:
            raise NotFoundError('unsupported signature method in BasicAuthProvider', method=method_name)

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
 