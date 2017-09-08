import pytest
from iotile.core.exceptions import ArgumentError
from iotile.cloud.utilities import device_slug_to_id, device_id_to_slug


def test_device_slug_to_id():
    """Convert a string device slug to a number."""

    assert device_slug_to_id('d--0000-0000-0000-0010') == 0x10
    assert device_slug_to_id('d--100a-0000-0000-0000') == 0x100a000000000000

    with pytest.raises(ArgumentError):
        device_slug_to_id('0000-0000-0000-0000')

    with pytest.raises(ArgumentError):
        device_slug_to_id('t--0000-0000-0000-0000')

    with pytest.raises(ArgumentError):
        device_slug_to_id('t--0000-0000-0000-0g00')

    with pytest.raises(ArgumentError):
        device_slug_to_id(0x100)

def test_device_id_to_slug():
    assert device_id_to_slug('0x10') == 'd--0000-0000-0000-0010'
    assert device_id_to_slug('1234 aBcD 5678 Ef90') == 'd--1234-abcd-5678-ef90'

    with pytest.raises(ArgumentError):
        device_id_to_slug('12345678901234567')

    with pytest.raises(ArgumentError):
        device_id_to_slug('non hexa chars')

    with pytest.raises(ArgumentError):
        device_slug_to_id(1234)
