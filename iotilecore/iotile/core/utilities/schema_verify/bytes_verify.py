import base64
import binascii
from verifier import Verifier
from iotile.core.exceptions import ValidationError, ArgumentError


class BytesVerifier(Verifier):
    """Verify that an object is a (possibly encoded) buffer of octets

    Args:
        desc (string): A description of the verifier
        encoding (string): A supported encoding of the bytes, currently must be
            one of base64, hex or none.  If None is given, the object must be
            a bytearray type object
    """

    def __init__(self, encoding='none', desc=None):
        super(BytesVerifier, self).__init__(desc)

        known_encodings = ['base64', 'hex', 'none']
        if encoding not in known_encodings:
            raise ArgumentError("Invalid encoding for bytes", known_encodings=known_encodings)

        self.encoding = encoding

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Returns:
            bytes or byterray: The decoded byte buffer

        Raises:
            ValidationError: If there is a problem verifying the object, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if self.encoding == 'none' and not isinstance(obj, (bytes, bytearray)):
            raise ValidationError('Byte object was not either bytes or a bytearray', type=obj.__class__.__name__)
        elif self.encoding == 'base64':
            try:
                data = base64.b64decode(obj)
                return data
            except TypeError:
                raise ValidationError("Could not decode base64 encoded bytes", obj=obj)
        elif self.encoding == 'hex':
            try:
                data = binascii.unhexlify(obj)
                return data
            except TypeError:
                raise ValidationError("Could not decode hex encoded bytes", obj=obj)

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier

        Returns:
            string: A formatted string
        """

        name = self.format_name('Bytes', indent_size)
        return self.wrap_lines(name, indent_level, indent_size)
