"""Generic wrapper around a Bluetooth Advertisement including optional scan response data.

All bluetooth advertisements are divided into typed fields.

The ``BLEAdvertisement`` class implements decoders for known field types as well as
validation logic to ensure the advertisement is conformant and not corrupted.
"""

from typing import Optional, Set, Dict
import uuid
import struct
from ..defines import AdElementType, compact_uuid, expand_uuid


class BLEAdvertisement:
    """Data class for a Bluetooth 4.0+ advertisement packet.

    If the advertisement contains a scan response packet, that is included as
    well in the same BLEAdvertisement class.  Convience parsing is performed
    so that individual data fields inside the advertisement can be checked and
    iterated over.

    Args:
        sender: The MAC address of the device sending this advertisement
        kind: The BLE defined advertisement packet type
        rssi: The RSSI signal strength of the received packet
        advert: The raw advertisement data contents
        scan_response: If there was a scan request performed, the scan response contents.
    """

    def __init__(self, sender: str, kind: int, rssi: float, advert: bytes,
                 scan_response: Optional[bytes] = None):
        self.sender = sender
        self.rssi = rssi
        self.advertisement = advert
        self.scan_response = scan_response
        self.kind = kind
        self._elements = None  # type: Optional[Dict[int, bytes]]
        self._services = None  # type: Optional[Set[uuid.UUID]]

    @property
    def elements(self) -> Dict[int, bytes]:
        """The parsed bluetooth ad elements in the advertisement."""

        if self._elements is None:
            self._elements = {}
            for ad_type, contents in self._iter_elements():
                if ad_type not in self._elements:
                    self._elements[ad_type] = contents
                else:
                    extra_content = _prepare_join(ad_type, contents)
                    if extra_content is not None:
                        self._elements[ad_type] += extra_content

        return self._elements

    @property
    def services(self) -> Set[uuid.UUID]:
        """Return the list of services mentioned in the advertisement."""

        if self._services is None:
            self._services = set(_extract_services(self.elements))

        return self._services

    def contains_service(self, service_uuid: uuid.UUID) -> bool:
        """Check if this advertisement includes a specific service UUID.

        This can be used to see if the device is compatible with a given
        profile. Note that service uuids can be encoded as either 2, 4 or 16
        byte objects. This method always checks for the most compact
        representation only.

        Args:
            service_uuid: The UUID to check for.
        """

        return service_uuid in self.services

    def service_data(self, service_uuid: uuid.UUID) -> Optional[bytes]:
        """Check if this advertisement includes service data for a specific service.

        The service data must be packed with the smallest possible
        representation of the service UUID.  So if it is a 16-bit uuid, then a
        SERVICE_DATA_UUID_16 is checked.  Larger uuids are not yet supported.
        """

        short_uuid = compact_uuid(service_uuid)
        if len(short_uuid) != 2:
            raise ValueError("UUIDs longer than 2 bytes are not currently supported, len=%d" % len(short_uuid))

        data = self.elements.get(AdElementType.SERVICE_DATA_UUID_16)
        if data is None:
            return None

        if len(data) < 2:
            return None

        service_id = data[:2]
        if short_uuid != service_id:
            return None

        return data[2:]

    def manufacturer_data(self, manufacturer: int) -> Optional[bytes]:
        """Fetch the manufacturer data from a specific manufacturer.

        If the given manufacturer is not present, None is returned.
        """

        manu = self.elements.get(AdElementType.MANUFACTURER_DATA)
        if manu is None:
            return None

        if len(manu) < 2:
            return None

        manu_id, = struct.unpack_from("<H", manu)
        if manu_id != manufacturer:
            return None

        return manu[2:]

    def _iter_elements(self):
        """Iterate over all ad elements inside an advertisement.

        All bluetooth advertisements are composed of a list of typed elements.
        This method lets you iterate over the elements that you care about,
        by type.

        Yields:
            The ad elements with their types and data.
        """

        yield from _iter_elements(self.advertisement)

        if self.scan_response is not None:
            yield from _iter_elements(self.scan_response)


_SERVICE_ELEMENTS = {
    # AD element type: size of each UUID, is it an array?
    AdElementType.INCOMPLETE_UUID_16_LIST: (2, True),
    AdElementType.COMPLETE_UUID_16_LIST: (2, True),
    AdElementType.INCOMPLETE_UUID_32_LIST: (4, True),
    AdElementType.COMPLETE_UUID_32_LIST: (4, True),
    AdElementType.INCOMPLETE_UUID_128_LIST: (16, True),
    AdElementType.COMPLETE_UUID_128_LIST: (16, True),
    AdElementType.SERVICE_DATA_UUID_16: (2, False),
    AdElementType.SERVICE_DATA_UUID_32: (4, False),
    AdElementType.SERVICE_DATA_UUID_128: (16, False)
}

_SERVICE_NAMES = frozenset(_SERVICE_ELEMENTS)

def _extract_services(elements):
    for ad_type, contents in elements.items():
        if ad_type not in _SERVICE_NAMES:
            continue

        size, is_list = _SERVICE_ELEMENTS[ad_type]

        for compressed_service in _iter_chunks(contents, size, is_list):
            yield expand_uuid(compressed_service)


def _iter_chunks(contents, size, allow_many=True):
    """Iterate over fixed size chunks of an array."""

    for i in range(0, len(contents), size):
        chunk = contents[i:i + size]
        if len(chunk) != size:
            return

        yield chunk

        if not allow_many:
            return


def _iter_elements(data: bytes):
    i = 0

    while i < len(data):
        length = data[i]

        if length == 0:
            return

        if i == len(data) - 1:
            return

        ad_type = data[i + 1]
        element = data[i + 2: i + length + 1]

        try:
            ad_type = AdElementType(ad_type)
        except ValueError:
            pass

        yield ad_type, element

        i += length + 1


# Map of joinable AD types and the prefix discard length for each one
_JOINABLE_AD_TYPES = {
    AdElementType.SERVICE_DATA_UUID_16: 2,
    AdElementType.SERVICE_DATA_UUID_32: 4,
    AdElementType.SERVICE_DATA_UUID_128: 16,
    AdElementType.MANUFACTURER_DATA: 2
}

def _prepare_join(ad_type, contents):
    """Strip redundant information from an ad element for concatenation.

    For example, manufacturer data starts with a 2 byte manufacturer id.
    When joining two adjacent manufacturer data elements, the second id
    should be stripped.

    Not all ad elements are allowed to have multiple copies in a single
    advertisement, so those are discarded if found.
    """

    join_size = _JOINABLE_AD_TYPES.get(ad_type)
    if join_size is None:
        return None

    return contents[join_size:]
