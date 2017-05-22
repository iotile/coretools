import pytest
from iotile.core.exceptions import ArgumentError
from iotile.sg.model import DeviceModel


def test_default_values():
    """Make sure we can get properties with default values."""

    model = DeviceModel()

    assert model.get('max_nodes') == 32
    assert model.get(u'max_nodes') == 32

    model.set('max_nodes', 16)
    assert model.get('max_nodes') == 16
    assert model.get(u'max_nodes') == 16

    model.set(u'max_nodes', 17)
    assert model.get('max_nodes') == 17
    assert model.get(u'max_nodes') == 17

    with pytest.raises(ArgumentError):
        model.get('unknown_parameter')

    with pytest.raises(ArgumentError):
        model.set('unknown_parameter', 15)
