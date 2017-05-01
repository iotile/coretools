from verifier import Verifier
from iotile.core.exceptions import ValidationError


class LiteralVerifier(Verifier):
    """Verify that an object is equal to a literal

    Args:
        literal (object): A literal value to be checked
        desc (string): A description of the verifier
    """

    def __init__(self, literal, desc=None):
        super(LiteralVerifier, self).__init__(desc)
        self._literal = literal

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if obj != self._literal:
            raise ValidationError("Object is not equal to literal", reason='%s is not equal to %s' % (str(obj), str(self._literal)), object=obj)

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier

        Returns:
            string: A formatted string
        """

        name = self.format_name('Literal', indent_size)

        if self.long_desc is not None:
            name += '\n'

        name += self.wrap_lines('value: %s\n' % str(self._literal), 1, indent_size)

        return self.wrap_lines(name, indent_level, indent_size)
