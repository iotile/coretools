import pytest
from iotile.core.utilities.schema_verify import DictionaryVerifier, Verifier, ListVerifier, StringVerifier, IntVerifier, BooleanVerifier, LiteralVerifier, OptionsVerifier
from iotile.core.exceptions import ValidationError


def test_format_short_only():
    """ Make sure names are properly formatted with short descs
    """

    short_only_desc = "this is a short desc"

    ver = Verifier(short_only_desc)
    val = ver.format_name('Test')

    assert val == 'Test: this is a short desc\n'


def test_format_long_only():
    """ Make sure names are properly formatted
    """

    long_only_desc = "this is a longer desc\nhello, this is line 2"

    ver = Verifier(long_only_desc)
    val = ver.format_name('Test')

    assert val == 'Test\n' + '    ' + 'this is a longer desc\n' + '    ' + 'hello, this is line 2\n'


def test_format_short_long():
    """Make sure names with both short and long desc are formatted correctly
    """

    short_long = "short desc\n\nthis is a longer desc\nhello, this is line 2"

    ver = Verifier(short_long)
    val = ver.format_name('Test')

    assert val == 'Test: short desc\n' + '    ' + 'this is a longer desc\n' + '    ' + 'hello, this is line 2\n'


def test_desc_cleanup():
    """Make sure descriptions are properly cleaned of whitespace
    """

    desc = """
    short desc

    long form desc starts here
    """

    ver = Verifier(desc)
    val = ver.format_name('Test')

    assert val == 'Test: short desc\n' + '    ' + 'long form desc starts here\n'


def test_int_formatting():
    ver = IntVerifier('short desc')

    val = ver.format(0)

    assert val == 'Integer: short desc\n'


def test_literal_formatting():
    ver = LiteralVerifier(1, 'short desc')

    val = ver.format(0)
    assert val == 'Literal: short desc\n    value: 1\n'


def test_boolean_formatting():
    ver1 = BooleanVerifier(desc='short desc')
    ver2 = BooleanVerifier(require_value=True, desc='short desc')
    ver3 = BooleanVerifier(require_value=False, desc='short desc\n\nlong desc1\nlong desc2')

    val1 = ver1.format(0)
    val2 = ver2.format(0)
    val3 = ver3.format(0)

    assert val1 == 'Boolean: short desc\n'
    assert val2 == 'Boolean: short desc\n    must be true\n'
    assert val3 == 'Boolean: short desc\n    long desc1\n    long desc2\n\n    must be false\n'
