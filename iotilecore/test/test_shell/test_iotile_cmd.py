from iotile.core.scripts.iotile_script import main


def test_basic_functionality():
    """Make sure that we can load and quit the shell."""

    assert main(['quit']) == 0


def test_unicode_strings():
    """Make sure that unicode strings are properly parsed."""

    assert main([u'quit']) == 0


def test_components():
    """Make sure that we can call non-builtin functions."""

    assert main(['registry', 'list_components']) == 0
