import re
from .verifier import Verifier
from iotile.core.exceptions import ValidationError


class DictionaryVerifier(Verifier):
    """Verify the keys and values in a Dictionary

    Args:
        desc (string): A description of what this dictionary should contain
        fixed_length (int): An optional restriction on exactly how many keys
            can be included in the dict.
    """

    def __init__(self, desc=None, fixed_length=None):
        super(DictionaryVerifier, self).__init__(desc)

        self._required_keys = {}
        self._optional_keys = {}
        self._additional_key_rules = []
        self._fixed_length = fixed_length

    def add_required(self, key, verifier):
        """Add a required key by name

        Args:
            key (string): The key name to match
            verifier (Verifier): The verification rule
        """

        self._required_keys[key] = verifier

    def add_optional(self, key, verifier):
        """Add an optional key by name

        Args:
            key (string): The key name to match
            verifier (Verifier): The verification rule
        """

        self._optional_keys[key] = verifier

    def key_rule(self, regex, verifier):
        """Add a rule with a pattern that should apply to all keys.

        Any key not explicitly listed in an add_required or add_optional rule
        must match ONE OF the rules given in a call to key_rule().
        So these rules are all OR'ed together.

        In this case you should pass a raw string specifying a regex that is
        used to determine if the rule is used to check a given key.


        Args:
            regex (str): The regular expression used to match the rule or None
                if this should apply to all
            verifier (Verifier): The verification rule
        """

        if regex is not None:
            regex = re.compile(regex)

        self._additional_key_rules.append((regex, verifier))

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        out_obj = {}

        if not isinstance(obj, dict):
            raise ValidationError("Invalid dictionary", reason="object is not a dictionary")

        if self._fixed_length is not None and len(obj) != self._fixed_length:
            raise ValidationError("Dictionary did not have the correct length", expected_length=self._fixed_length, actual_length=self._fixed_length)

        unmatched_keys = set(obj.keys())
        required_keys = set(self._required_keys.keys())

        # First check and make sure that all required keys are included and verify them
        for key in required_keys:
            if key not in unmatched_keys:
                raise ValidationError("Required key not found in dictionary", reason="required key %s not found" % key, key=key)

            out_obj[key] = self._required_keys[key].verify(obj[key])
            unmatched_keys.remove(key)

        # Now check and see if any of the keys in the dictionary are optional and check them
        to_remove = set()
        for key in unmatched_keys:
            if key not in self._optional_keys:
                continue

            out_obj[key] = self._optional_keys[key].verify(obj[key])
            to_remove.add(key)

        unmatched_keys -= to_remove

        # If there are additional keys, they need to match at least one of the additional key rules
        if len(unmatched_keys) > 0:
            if len(self._additional_key_rules) == 0:
                raise ValidationError("Extra key found in dictionary that does not allow extra keys", reason="extra keys found that were not expected", keys=unmatched_keys)

            to_remove = set()
            for key in unmatched_keys:
                for key_match, rule in self._additional_key_rules:
                    if key_match is None or key_match.matches(key):
                        out_obj[key] = rule.verify(obj[key])
                        to_remove.add(key)
                        break

            unmatched_keys -= to_remove

            if len(unmatched_keys) > 0:
                raise ValidationError("Extra key found in dictionary that did not match any extra key rule", reason="extra keys found that did not match any rule", keys=unmatched_keys)

        return out_obj
