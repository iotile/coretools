from verifier import Verifier
from iotile.core.exceptions import ValidationError


class BooleanVerifier(Verifier):
    """Verify that an object is a boolean

    Args:
        desc (string): A description of the verifier
        require_value (bool): Require a specific True or False value
    """

    def __init__(self, require_value=None, desc=None):
        super(BooleanVerifier, self).__init__(desc)
        self._require_value = require_value

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if not isinstance(obj, bool):
            raise ValidationError("Object is not a bool", reason='object is not a bool', object=obj)

        if self._require_value is not None and obj != self._require_value:
            raise ValidationError("Boolean is not equal to specified literal", reason='boolean value %s should be %s' % (str(obj), str(self._require_value)))

        return obj

    def format(self, indent_level, indent_size=4):
        """Format this verifier

        Returns:
            string: A formatted string
        """

        name = self.format_name('Boolean', indent_size)

        if self._require_value is not None:
            if self.long_desc is not None:
                name += '\n'

            name += self.wrap_lines('must be %s\n' % str(self._require_value).lower(), 1, indent_size)

        return self.wrap_lines(name, indent_level, indent_size)
