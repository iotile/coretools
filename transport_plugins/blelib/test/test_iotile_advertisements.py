"""Tests to ensure that we can generate and parse iotile advertisements correctly."""

from iotile.core.hw.reports import IOTileReading
from iotile_transport_blelib.iotile.advertisements import generate_v1_advertisement, generate_v2_advertisement
from iotile_transport_blelib.iotile import TileBusService, ARCH_MANUFACTURER, IOTILE_SERVICE_UUID
from iotile_transport_blelib.interface import BLEAdvertisement

def test_v1_advertisement_gen_basic():
    """Make sure we can generate a valid v1 advertisement."""

    advert_data, scan_data = generate_v1_advertisement(0xabcd)

    advert = BLEAdvertisement('00:11:22:33:44:55', 0, -55, advert_data, scan_data)

    for elem, value in advert.elements.items():
        print("%s: %r" % (elem, value))

    assert TileBusService.UUID in advert.services
    assert advert.contains_service(TileBusService.UUID)

    manu = advert.manufacturer_data(ARCH_MANUFACTURER)
    assert manu is not None
    assert len(manu) == 24


def test_v1_advert_no_scan_response():
    """Make sure we correctly parse v1 advertisements without scan response."""

    advert_data, _scan_data = generate_v1_advertisement(0xabcd)

    advert = BLEAdvertisement('00:11:22:33:44:55', 0, -55, advert_data)

    assert TileBusService.UUID in advert.services
    assert advert.contains_service(TileBusService.UUID)

    manu = advert.manufacturer_data(ARCH_MANUFACTURER)
    assert manu is not None
    assert len(manu) == 6


def test_v1_advertisement_gen_bcast():
    """Make sure we can broadcast data in a v1 advertisement."""

    reading = IOTileReading(0, 0x5001, 100)
    _advert, scan_data = generate_v1_advertisement(0xabcd, broadcast=reading)
    assert len(scan_data) == 31


def test_v2_advert_no_encryption():
    """Make sure we can correctly generate a v2 advertisement."""

    advert_data = generate_v2_advertisement(0xabcd)
    advert = BLEAdvertisement('00:11:22:33:44:55', 0, -55, advert_data)

    assert IOTILE_SERVICE_UUID in advert.services
    assert advert.contains_service(IOTILE_SERVICE_UUID)

    data = advert.service_data(IOTILE_SERVICE_UUID)
    assert len(data) == 24

