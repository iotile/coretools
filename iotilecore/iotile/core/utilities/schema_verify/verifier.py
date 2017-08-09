"""A recursive verifier that verifies the schema of a python dictionary

This is similar to the concept of a JSON schema verifier but with more expressive
verification steps and works on dictionaries produced from a variety of sources.
"""

import inspect
from copy import deepcopy
from iotile.core.exceptions import ValidationError

class Verifier(object):
    """A base class for verifing that an object conforms to a schema

    Subclasses should override the verify function to actually verify the
    object that is passed in.

    Args:
        desc (string): An optional block description of what this verifier is
            checking.
    """

    def __init__(self, desc=None):
        self.short_desc = None
        self.long_desc = None
        self.description = None
        if desc is not None:
            self.set_description(desc)

    def clone(self):
        """Clone this verifier.

        This function is useful for implementing hierarch among verifiers
        where one or more of the verification steps is shared.

        For example, a dict that always has key1 and key2 can be pulled
        into a single DictVerifier and cloned for each variant of the dict.
        """

        return deepcopy(self)

    def set_description(self, desc):
        self.description = inspect.cleandoc(desc)

        self.short_desc = self._get_short_description()
        self.long_desc = self._get_long_description()

    def matches(self, obj):
        """Return True if object matches this verifier."""

        try:
            self.verify(obj)
            return True
        except ValidationError:
            return False

    def verify(self, obj):
        """Verify that the object conforms to this verifier's schema.

        Args:
            obj (object): A python object to verify

        Raises:
            ValidationError: If there is a problem verifying the dictionary, a
                ValidationError is thrown with at least the reason key set indicating
                the reason for the lack of validation.
        """

        return obj

    def _get_short_description(self):
        """Return the first line of a multiline description

        Returns:
            string: The short description, otherwise None
        """

        if self.description is None:
            return None

        lines = [x for x in self.description.split('\n')]
        if len(lines) == 1:
            return lines[0]
        elif len(lines) >= 3 and lines[1] == '':
            return lines[0]

        return None

    def _get_long_description(self):
        """Return the subsequent lines of a multiline description

        Returns:
            string: The long description, otherwise None
        """

        if self.description is None:
            return None

        lines = [x for x in self.description.split('\n')]
        if len(lines) == 1:
            return None

        elif len(lines) >= 3 and lines[1] == '':
            return '\n'.join(lines[2:])

        return self.description

    def wrap_lines(self, text, indent_level, indent_size=4):
        """Indent a multiline string

        Args:
            text (string): The string to indent
            indent_level (int): The number of indent_size spaces to prepend
                to each line
            indent_size (int): The number of spaces to prepend for each indent
                level

        Returns:
            string: The indented block of text
        """

        indent = ' '*indent_size*indent_level
        lines = text.split('\n')

        wrapped_lines = []

        for line in lines:
            if line == '':
                wrapped_lines.append(line)
            else:
                wrapped_lines.append(indent + line)

        return '\n'.join(wrapped_lines)

    def format_name(self, name, indent_size=4):
        """Format the name of this verifier

        The name will be formatted as:
            <name>: <short description>
                long description if one is given followed by \n
                otherwise no long description

        Args:
            name (string): A name for this validator
            indent_size (int): The number of spaces to indent the
                description
        Returns:
            string: The formatted name block with a short and or long
                description appended.
        """

        name_block = ''

        if self.short_desc is None:
            name_block += name + '\n'
        else:
            name_block += name + ': ' + self.short_desc + '\n'

        if self.long_desc is not None:
            name_block += self.wrap_lines(self.long_desc, 1, indent_size=indent_size)
            name_block += '\n'

        return name_block

    def trim_whitespace(self, text):
        """Remove leading whitespace from each line of a multiline string

        Args:
            text (string): The text to be unindented

        Returns:
            string: The unindented block of text
        """

        lines = text.split('\n')
        new_lines = [x.lstrip() for x in lines]

        return '\n'.join(new_lines)
