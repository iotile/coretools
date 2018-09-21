import pytest
from past.builtins import long
from iotile.core.exceptions import ArgumentError
from iotile.cloud.utilities import *


def test_device_slug_to_id():
    """Convert a string device slug to a number."""

    assert device_slug_to_id('d--0000-0000-0000-0010') == 0x10
    assert device_slug_to_id('d--0010') == 0x10

    with pytest.raises(ArgumentError):
        # Only 48bits allowed
        device_slug_to_id('d--1234-0000-0000-0001')

    # Null device is now acceptable
    #with pytest.raises(ArgumentError):
    #    device_slug_to_id('0000-0000-0000-0000')

    with pytest.raises(ArgumentError):
        device_slug_to_id('t--0000-0000-0000-0000')

    with pytest.raises(ArgumentError):
        device_slug_to_id('t--0000-0000-0000-0g00')

    with pytest.raises(ArgumentError):
        device_slug_to_id(0x100)


def test_device_id_to_slug():
    """Ensure we can convert device ids to slugs."""

    assert device_id_to_slug(0x10) == 'd--0000-0000-0000-0010'
    assert device_id_to_slug('d--0010') == 'd--0000-0000-0000-0010'
    assert device_id_to_slug('0010') == 'd--0000-0000-0000-0010'
    assert device_id_to_slug(0xabcd5678ef90) == 'd--0000-abcd-5678-ef90'
    assert device_id_to_slug(long(0x1234)) == 'd--0000-0000-0000-1234'

    with pytest.raises(ArgumentError):
        device_id_to_slug('string')

    with pytest.raises(ArgumentError):
        # Only 48bits allowed
        device_id_to_slug(pow(16,12))

    with pytest.raises(ArgumentError):
        device_slug_to_id(-5)


def test_fleet_id_to_slug():
    """Ensure we can convert device ids to slugs."""

    assert fleet_id_to_slug(0x10) == 'g--0000-0000-0010'
    assert fleet_id_to_slug('g--0010') == 'g--0000-0000-0010'
    assert fleet_id_to_slug('0010') == 'g--0000-0000-0010'
    assert fleet_id_to_slug(0xabcd5678ef90) == 'g--abcd-5678-ef90'
    assert fleet_id_to_slug(long(0x1234)) == 'g--0000-0000-1234'

    with pytest.raises(ArgumentError):
        fleet_id_to_slug('string')

    with pytest.raises(ArgumentError):
        # Only 48bits allowed
        fleet_id_to_slug(pow(16,12))

    with pytest.raises(ArgumentError):
        fleet_id_to_slug(-5)
