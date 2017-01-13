import hashlib
import hmac
import struct
import os
from auth_provider import AuthProvider, KnownSignatureMethods
from iotile.core.exceptions import NotFoundError

class EnvAuthProvider(AuthProvider):
    """Basic authentication provider that can sign and verify using user keys

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
            key = key_var.decode('hex')
        except ValueError:
            raise NotFoundError("User key in variable could not be decoded from hex", device_id=device_id, key_value=key_var)

        if len(key) != 32:
            raise NotFoundError("User key in variable is not the correct length, should be 64 hex characters", device_id=device_id, key_value=key_var)

        return key

    def sign(self, device_id, sig_method, data):
        """Sign a buffer of data on behalf of a device

        This routine only supports user key based signing

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

        if method_name == 'hmac_sha256_user_key':
            key = self._get_key(device_id)
            hmac_calc = hmac.new(key, data, hashlib.sha256)
            result = bytearray(hmac_calc.digest())
        else:
            raise NotFoundError('unsupported signature method in EnvAuthProvider', method=method_name)

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

        if method_name == 'hmac_sha256_user_key':
            key = self._get_key(device_id)
            hmac_calc = hmac.new(key, data, hashlib.sha256)
            result = bytearray(hmac_calc.digest())
        else:
            raise NotFoundError('unsupported signature method in EnvAuthProvider', method=method_name)

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
 