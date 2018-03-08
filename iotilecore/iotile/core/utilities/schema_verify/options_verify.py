from .verifier import Verifier
from iotile.core.exceptions import ValidationError


class OptionsVerifier(Verifier):
    """Verify that an object is one of a set of options

    Args:
        *args (Verifier): A set of possible values to compare
        desc (string): A description of the verifier
    """

    def __init__(self, *args, **kwargs):
        desc = kwargs.get('desc', None)
        super(OptionsVerifier, self).__init__(desc)

        self._options = args

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        if len(self._options) == 0:
            raise ValidationError("No options", reason='no options given in options verifier, matching not possible', object=obj)

        exceptions = {}

        for i, option in enumerate(self._options):
            try:
                obj = option.verify(obj)
                return obj
            except ValidationError as exc:
                exceptions['option_%d' % (i+1)] = exc.params['reason']

        raise ValidationError("Object did not match any of a set of options", reason="object did not match any given option (first failure = '%s')" % exceptions['option_1'], **exceptions)
