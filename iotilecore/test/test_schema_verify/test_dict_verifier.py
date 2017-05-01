import pytest
from iotile.core.utilities.schema_verify import BytesVerifier, DictionaryVerifier, ListVerifier, StringVerifier, IntVerifier, BooleanVerifier, LiteralVerifier, OptionsVerifier
from iotile.core.exceptions import ValidationError


@pytest.fixture
def verifier1():
    ver = DictionaryVerifier('test verifier')
    ver.add_required('req_key', DictionaryVerifier())
    ver.add_optional('opt_key', ListVerifier(StringVerifier('a string')))
    ver.add_optional('opt2_key', BooleanVerifier(desc='a boolean'))
    return ver


@pytest.fixture
def dict1():
    dict1 = {}
    dict1['req_key'] = {}
    dict1['opt_key'] = ['a', 'b', 'c']
    dict1['opt2_key'] = True
    return dict1


def test_dict_verifier(verifier1, dict1):
    """Make sure dict verification works
    """

    verifier1.verify(dict1)


def test_dict_noreq(verifier1):
    """Make sure a missing required key is found
    """

    dict1 = {}
    #dict1['req_key'] = {}
    dict1['opt_key'] = ['a', 'b', 'c']
    dict1['opt2_key'] = True
    return dict1


    with pytest.raises(ValidationError):
        verifier1.verify(dict1)

def test_dict_noopt2(verifier1):
    """Make sure a missing optional key is not a cause of problems
    """

    dict1 = {}
    dict1['req_key'] = {}
    dict1['opt_key'] = ['a', 'b', 'c']
    #dict1['opt2_key'] = True

    verifier1.verify(dict1)


def test_dict_noopt(verifier1):
    """Make sure a missing optional key is not a cause of problems
    """

    dict1 = {}
    dict1['req_key'] = {}
    #dict1['opt_key'] = ['a', 'b', 'c']
    dict1['opt2_key'] = True

    verifier1.verify(dict1)


def test_dict_wrongopt(verifier1):
    """Make sure an optional key with the wrong schema is found
    """

    dict1 = {}
    dict1['req_key'] = {}
    #dict1['opt_key'] = ['a', 'b', 'c']
    dict1['opt2_key'] = "hello"

    with pytest.raises(ValidationError):
        verifier1.verify(dict1)


def test_options_verifier():
    """Check and make sure that OptionsVerifier works
    """

    value = 'abc'

    verifier = OptionsVerifier(IntVerifier('int'), StringVerifier('string'))
    verifier.verify(value)

    verifier = OptionsVerifier(LiteralVerifier('abc'))
    verifier.verify(value)

    with pytest.raises(ValidationError):
        verifier.verify('ab')

    with pytest.raises(ValidationError):
        verifier.verify(1)

def test_bytes_decoding():
    """Check to make sure that decoding bytes works."""

    instring = 'zasAAA=='
    verifier = BytesVerifier(encoding='base64')

    out1 = verifier.verify(instring)
    assert len(out1) == 4

    verifier = BytesVerifier(encoding='hex')
    out2 = verifier.verify('cdab0000')
    assert len(out2) == 4

    assert out1 == out2
