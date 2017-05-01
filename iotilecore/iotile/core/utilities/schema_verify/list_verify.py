from verifier import Verifier
from iotile.core.exceptions import ValidationError


class ListVerifier(Verifier):
    """Verify the values in a List

    Args:
        desc (string): A description of what this list should contain
        verifier (Verifier): A verifier for what the list should contain.
            each entry in the list must match the same verifier.
        min_length (int): An optional minimum length for the list
        max_length (int): An optional maximum length for the list
    """

    def __init__(self, verifier, min_length=None, max_length=None, desc=None):
        super(ListVerifier, self).__init__(desc)

        self._min_length = min_length
        self._max_length = max_length
        self._verifier = verifier

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        out_obj = []
        if self._min_length is not None and len(obj) < self._min_length:
            raise ValidationError("List was too short", reason="list length %d was less than the minimum %d" % (len(obj), self._min_length), min_length=self._min_length, actual_length=len(obj))

        if self._max_length is not None and len(obj) > self._max_length:
            raise ValidationError("List was too long", reason="list length %d was greater than the maximum %d" % (len(obj), self._max_length), min_length=self._max_length, actual_length=len(obj))

        for val in obj:
            out_obj.append(self._verifier.verify(val))

        return out_obj
