from .verifier import Verifier
from iotile.core.exceptions import ValidationError


class NoneVerifier(Verifier):
    """Verify that an object is None

    Args:
        desc (string): A description of the verifier
    """

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if obj is not None:
            raise ValidationError("Object is not None",
                                  reason='%s is not None' % str(obj), object=obj)

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier

        Returns:
            string: A formatted string
        """

        name = self.format_name('None', indent_size)
        return self.wrap_lines(name, indent_level, indent_size)
