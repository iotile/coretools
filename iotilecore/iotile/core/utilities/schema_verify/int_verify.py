from builtins import int
from .verifier import Verifier
from iotile.core.exceptions import ValidationError


class IntVerifier(Verifier):
    """Verify that an object is a integer

    Args:
        desc (string): A description of the verifier
    """

    def __init__(self, desc=None):
        super(IntVerifier, self).__init__(desc)

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if not isinstance(obj, int):
            raise ValidationError("Object is not a int", reason='object is not a int', object=obj, type=type(obj), int_type=int)

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier

        Returns:
            string: A formatted string
        """

        name = self.format_name('Integer', indent_size)
        return self.wrap_lines(name, indent_level, indent_size)
