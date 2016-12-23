import pytest
from iotile.core.exceptions import ArgumentError
from iotile.core.dev.registry import ComponentRegistry

def test_nonexistent():
    """Make sure nonexistent config vars throw an error
    """

    reg = ComponentRegistry()

    with pytest.raises(ArgumentError):
        reg.get_config('test1_nonexistent')

def test_create_delete():
    """Make sure we can create, fetch and delete config vars
    """
    reg = ComponentRegistry()

    reg.set_config('test1', 'hello')

    val = reg.get_config('test1')
    assert val == 'hello'

    reg.set_config('test1', 'hello2')
    val = reg.get_config('test1')
    assert val == 'hello2'

    reg.clear_config('test1')

    with pytest.raises(ArgumentError):
        reg.get_config('test1')
