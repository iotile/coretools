from iotile.core.exceptions import ValidationError
from .verifier import Verifier


class EnumVerifier(Verifier):
    """Verify that an object is one of a list of literal options.

    Args:
        desc (string): A description of the verifier
    """

    def __init__(self, options, desc=None):
        super(EnumVerifier, self).__init__(desc)
        self.options = options

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema.

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the object, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if obj not in self.options:
            raise ValidationError("Object is not in list of enumerated options", reason='not in list of enumerated options', object=obj, options=self.options)

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier.

        Returns:
            string: A formatted string
        """

        name = self.format_name('Enumeration', indent_size)
        return self.wrap_lines(name, indent_level, indent_size)
