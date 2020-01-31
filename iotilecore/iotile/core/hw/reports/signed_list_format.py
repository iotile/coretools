"""IOTileReport subclass for readings packaged as individual readings"""

import datetime
import struct
import hashlib
import hmac
from enum import IntEnum
from .report import IOTileReport, IOTileReading
from iotile.core.utilities.packed import unpack
from iotile.core.exceptions import NotFoundError, ExternalError
from iotile.core.hw.auth.auth_provider import AuthProvider
from iotile.core.hw.auth.auth_chain import ChainedAuthProvider

class ReportSignatureFlags(IntEnum):
    """Types of stream report signature"""
    SIGNED_WITH_HASH = 0
    SIGNED_WITH_USER_KEY = 1
    SIGNED_WITH_DEVICE_KEY = 2

class SignedListReport(IOTileReport):
    """A report that consists of a signed list of readings.

    Args:
        rawreport (bytearray): The raw data of this report
    """

    ReportType = 1

    def __init__(self, rawreport, **kwargs):
        super(SignedListReport, self).__init__(rawreport, signed=True, encrypted=False, **kwargs)

    @classmethod
    def KeyTypeToStreamType(cls, key_type):
        """Converts key type into the type of signed report that can be encrypted with this key

        Args:
            int: a type of the key, see AuthProvider

        Returns:
            ReportSignatureFlags: a type of the stream report
        """
        if key_type == AuthProvider.NoKey:
            return ReportSignatureFlags.SIGNED_WITH_HASH
        elif key_type == AuthProvider.UserKey:
            return ReportSignatureFlags.SIGNED_WITH_USER_KEY
        elif key_type == AuthProvider.DeviceKey:
            return ReportSignatureFlags.SIGNED_WITH_DEVICE_KEY
        else:
            raise ExternalError("Unsupported key type {}".format(key_type))

    @classmethod
    def StreamTypeToKeyType(cls, stream_type):
        """Converts the stream type into the key type that was used to encryped this stream report

        Args:
            ReportSignatureFlags: a type of the stream report

        Returns:
            int: type of key, see AuthProvider
        """

        if stream_type == ReportSignatureFlags.SIGNED_WITH_HASH:
            return AuthProvider.NoKey
        elif stream_type == ReportSignatureFlags.SIGNED_WITH_USER_KEY:
            return AuthProvider.UserKey
        elif stream_type == ReportSignatureFlags.SIGNED_WITH_DEVICE_KEY:
            return AuthProvider.DeviceKey
        else:
            raise ExternalError("Unsupported stream signature type {}".format(stream_type))

    @classmethod
    def HeaderLength(cls):
        """Return the length of a header needed to calculate this report's length

        Returns:
            int: the length of the needed report header
        """

        return 20

    @classmethod
    def ReportLength(cls, header):
        """Given a header of HeaderLength bytes, calculate the size of this report"""

        first_word, = unpack("<L", header[:4])

        length = (first_word >> 8)
        return length

    @classmethod
    def VerifyReport(cls, device_id, auth_provider, key_type, data, signature, **kwargs):
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

        if key_type == AuthProvider.NoKey:
            result = bytearray(hashlib.sha256(data).digest())
        else:
            report_key = auth_provider.get_serialized_key(key_type, device_id, **kwargs)

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

    @classmethod
    def DecryptReport(cls, device_id, auth_provider, key_type, data, **kwargs):
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

        report_key = auth_provider.get_serialized_key(key_type, device_id, **kwargs)

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

    @classmethod
    def EncryptReport(cls, device_id, auth_provider, key_type, data, **kwargs):
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

        report_key = auth_provider.get_serialized_key(key_type, device_id, **kwargs)

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

    @classmethod
    def SignReport(cls, device_id, auth_provider, key_type, data, **kwargs):
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

        if key_type == AuthProvider.NoKey:
            result = bytearray(hashlib.sha256(data).digest())
        else:
            report_key = auth_provider.get_serialized_key(key_type, device_id, **kwargs)

            # We sign the SHA256 hash of the message
            message_hash = hashlib.sha256(data).digest()
            hmac_calc = hmac.new(report_key, message_hash, hashlib.sha256)
            result = bytearray(hmac_calc.digest())

        return {'signature': result, 'root_key': key_type}


    @classmethod
    def FromReadings(cls, uuid, readings, root_key=AuthProvider.NoKey, signer=None,
                     report_id=IOTileReading.InvalidReadingID, selector=0xFFFF, streamer=0, sent_timestamp=0):
        """Generate an instance of the report format from a list of readings and a uuid.

        The signed list report is created using the passed readings and signed using the specified method
        and AuthProvider.  If no auth provider is specified, the report is signed using the default authorization
        chain.

        Args:
            uuid (int): The uuid of the deviec that this report came from
            readings (list): A list of IOTileReading objects containing the data in the report
            root_key (int): The key that should be used to sign the report (must be supported
                by an auth_provider)
            signer (AuthProvider): An optional preconfigured AuthProvider that should be used to sign this
                report.  If no AuthProvider is provided, the default ChainedAuthProvider is used.
            report_id (int): The id of the report.  If not provided it defaults to IOTileReading.InvalidReadingID.
                Note that you can specify anything you want for the report id but for actual IOTile devices
                the report id will always be greater than the id of all of the readings contained in the report
                since devices generate ids sequentially.
            selector (int): The streamer selector of this report.  This can be anything but if the report came from
                a device, it would correspond with the query the device used to pick readings to go into the report.
            streamer (int): The streamer id that this reading was sent from.
            sent_timestamp (int): The device's uptime that sent this report.
        """

        lowest_id = IOTileReading.InvalidReadingID
        highest_id = IOTileReading.InvalidReadingID

        report_len = 20 + 16*len(readings) + 24
        len_low = report_len & 0xFF
        len_high = report_len >> 8

        unique_readings = [x.reading_id for x in readings if x.reading_id != IOTileReading.InvalidReadingID]
        if len(unique_readings) > 0:
            lowest_id = min(unique_readings)
            highest_id = max(unique_readings)

        signature_flags = SignedListReport.KeyTypeToStreamType(root_key)
        header = struct.pack("<BBHLLLBBH", cls.ReportType, len_low, len_high, uuid, report_id,
                             sent_timestamp, signature_flags, streamer, selector)
        header = bytearray(header)

        packed_readings = bytearray()

        for reading in readings:
            packed_reading = struct.pack("<HHLLL", reading.stream, 0, reading.reading_id,
                                         reading.raw_time, reading.value)
            packed_readings += bytearray(packed_reading)

        footer_stats = struct.pack("<LL", lowest_id, highest_id)

        if signer is None:
            signer = ChainedAuthProvider()

        # If we are supposed to encrypt this report, do the encryption
        if root_key != signer.NoKey:
            enc_data = packed_readings

            try:
                result = SignedListReport.EncryptReport(uuid, signer, root_key, enc_data, report_id=report_id,
                                               sent_timestamp=sent_timestamp)
            except NotFoundError:
                raise ExternalError("Could not encrypt report because no AuthProvider supported "
                                    "the requested encryption method for the requested device",
                                    device_id=uuid, root_key=root_key)

            signed_data = header + result['data'] + footer_stats
        else:
            signed_data = header + packed_readings + footer_stats

        try:
            signature = SignedListReport.SignReport(uuid, signer, root_key, signed_data, report_id=report_id,
                                           sent_timestamp=sent_timestamp)
        except NotFoundError:
            raise ExternalError("Could not sign report because no AuthProvider supported the requested "
                                "signature method for the requested device", device_id=uuid, root_key=root_key)

        footer = struct.pack("16s", bytes(signature['signature'][:16]))
        footer = bytearray(footer)

        data = signed_data + footer
        return SignedListReport(data)

    def decode(self):
        """Decode this report into a list of readings
        """

        fmt, len_low, len_high, device_id, report_id, sent_timestamp, signature_flags, \
        origin_streamer, streamer_selector = unpack("<BBHLLLBBH", self.raw_report[:20])

        assert fmt == 1
        length = (len_high << 8) | len_low

        self.origin = device_id
        self.report_id = report_id
        self.sent_timestamp = sent_timestamp
        self.origin_streamer = origin_streamer
        self.streamer_selector = streamer_selector
        self.signature_flags = signature_flags

        assert len(self.raw_report) == length

        remaining = self.raw_report[20:]
        assert len(remaining) >= 24
        readings = remaining[:-24]
        footer = remaining[-24:]

        lowest_id, highest_id, signature = unpack("<LL16s", footer)
        signature = bytearray(signature)

        self.lowest_id = lowest_id
        self.highest_id = highest_id
        self.signature = signature

        signed_data = self.raw_report[:-16]
        signer = ChainedAuthProvider()

        key_type = self.StreamTypeToKeyType(signature_flags)
        self.encrypted = (key_type != AuthProvider.NoKey)

        try:
            verification = SignedListReport.VerifyReport(device_id, signer, key_type, signed_data, signature,
                                                report_id=report_id, sent_timestamp=sent_timestamp)
            self.verified = verification['verified']
        except NotFoundError:
            self.verified = False

        # If we were not able to verify the report, do not try to parse or decrypt it since we
        # can't guarantee who it came from.
        if not self.verified:
            return [], []

        # If the report is encrypted, try to decrypt it before parsing the readings
        if self.encrypted:
            try:
                result = SignedListReport.DecryptReport(device_id, signer, key_type, readings,
                                               report_id=report_id, sent_timestamp=sent_timestamp)
                readings = result['data']
            except NotFoundError:
                return [], []

        # Now parse all of the readings
        # Make sure this report has an integer number of readings
        assert (len(readings) % 16) == 0

        time_base = self.received_time - datetime.timedelta(seconds=sent_timestamp)
        parsed_readings = []

        for i in range(0, len(readings), 16):
            reading = readings[i:i+16]
            stream, _, reading_id, timestamp, value = unpack("<HHLLL", reading)

            parsed = IOTileReading(timestamp, stream, value, time_base=time_base, reading_id=reading_id)
            parsed_readings.append(parsed)

        return parsed_readings, []
