import pytest
import os
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.exceptions import ArgumentError


def tile_path(name):
    parent = os.path.dirname(__file__)
    path = os.path.join(parent, name)
    return path


@pytest.fixture(scope='function', params=['json', 'sqlite'])
def registry(request):
    ComponentRegistry.SetBackingStore(request.param)

    reg = ComponentRegistry()
    reg.clear()

    yield reg

    reg.clear()


def test_registry(registry):
    """Make sure all registry operations work
    """

    assert len(registry.list_components()) == 0

    with pytest.raises(ArgumentError):
        registry.get_component('unknown')

    registry.add_component(tile_path('devmode_component'))
    assert len(registry.list_components()) == 1

    # Make sure configs and components have a separate namespace
    with pytest.raises(ArgumentError):
        registry.get_config('devmode_component')

    registry.set_config('devmode_component', 'value')
    assert registry.get_config('devmode_component') == 'value'
    assert len(registry.list_components()) == 1

    registry.clear_components()
    assert len(registry.list_components()) == 0
    assert registry.get_config('devmode_component') == 'value'
    registry.clear()

    with pytest.raises(ArgumentError):
        registry.get_config('devmode_component')