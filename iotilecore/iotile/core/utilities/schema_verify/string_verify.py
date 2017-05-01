from verifier import Verifier
from iotile.core.exceptions import ValidationError


class StringVerifier(Verifier):
    """Verify that an object is a string

    Args:
        desc (string): A description of the verifier
    """

    def __init__(self, desc=None):
        super(StringVerifier, self).__init__(desc)

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if not isinstance(obj, basestring):
            raise ValidationError("Object is not a string", reason='object is not a string', object=obj)

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier

        Returns:
            string: A formatted string
        """

        desc = self.format_name('String')
        return self.wrap_lines(desc, indent_level, indent=indent_size)

