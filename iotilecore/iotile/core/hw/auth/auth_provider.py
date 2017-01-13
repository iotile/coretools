"""Auth providers are classes that can encrypt, decrypt, sign or verify data from IOTile devics

All auth providers must inherit from the AuthProvider class defined in this file and override the
methods that it provides with their own implementations.  
"""

import pkg_resources
from iotile.core.exceptions import NotFoundError, ArgumentError

HashOnlySHA256Signature = 0
HMACSHA256UserKey = 1
HMACSHA256FactoryKey = 2

KnownSignatureMethods = {
    HashOnlySHA256Signature:    'hash_only_sha256',        #Data is not signed, there is simply a sha256 integrity check
    HMACSHA256UserKey:          'hmac_sha256_user_key',    #Data is signed simply with HMAC using a user settable key on the device
    HMACSHA256FactoryKey:       'hmac_sha256_factory_key'  #Data is signed with HMAC using a factory set secret key associated with the device
}

class AuthProvider(object):
    """Base class for all objects that provide a way to authenticate or protect data
    
    Args:
        args (dict): An optional dictionary of AuthProvider specific config information
    """

    def __init__(self, args=None):
        if args is None:
            args = {}

        self.args = args

    @classmethod
    def FindByName(self, name):
        """
        """
        
        for entry in pkg_resources.iter_entry_points('iotile.auth_provider'):
            if entry.name == name:
                return entry.load()

    def encrypt(self, device_id, enc_method, data):
        """Encrypt a buffer of data on behalf of a device

        Args:
            device_id (int): The id of the device that we should encrypt for
            enc_method (int): The method of encryption that we should perform
            data (bytearray): The data that we should encrypt

        Returns:
            dict: The encrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        raise NotFoundError("encrypt method is not implemented")

    def decrypt(self, device_id, enc_method, data):
        """Decrypt a buffer of data on behalf of a device

        Args:
            device_id (int): The id of the device that we should encrypt for
            enc_method (int): The method of encryption that we should perform
            data (bytearray): The data that we should encrypt

        Returns:
            dict: The decrypted data and any associated metadata about the data.
                The data itself must always be a bytearray stored under the 'data'
                key, however additional keys may be present depending on the encryption method
                used.

        Raises:
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        raise NotFoundError("decrypt method is not implemented")

    def sign(self, device_id, sig_method, data):
        """Sign a buffer of data on behalf of a device

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
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        raise NotFoundError("sign method is not implemented")

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
            NotFoundError: If the auth provider is not able to encrypt the data.
        """

        raise NotFoundError("verify method is not implemented")

    def _check_signature_method(self, sig_method):
        if sig_method in KnownSignatureMethods:
            return True

        raise NotFoundError("unknown signature method", method=sig_method)