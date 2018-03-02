"""Common utility functions used across iotile.cloud packages."""

from iotile_cloud.utils.gid import IOTileDeviceSlug
from iotile.core.exceptions import ArgumentError


def device_slug_to_id(slug):
    """Convert a d-- device slug to an integer.

    Args:
        slug (str): A slug in the format d--XXXX-XXXX-XXXX-XXXX

    Returns:
        int: The device id as an integer

    Raises:
        ArgumentError: if there is a malformed slug
    """

    if not isinstance(slug, (str, unicode)):
        raise ArgumentError("Invalid device slug that is not a string", slug=slug)

    try:
        device_slug = IOTileDeviceSlug(slug)
    except Exception:
        raise ArgumentError("Unable to recognize {} as a device id".format(slug))

    return device_slug.get_id()


def device_id_to_slug(id):
    """ Converts a device id into a correct device slug.

    Args:
        id (long) : A device id
        id (string) : A device slug in the form of XXXX, XXXX-XXXX-XXXX-XXXX, d--XXXX, d--XXXX-XXXX-XXXX-XXXX
    Returns:
        str: The device slug in the d--XXXX-XXXX-XXXX-XXXX format
    Raises:
        ArgumentError: if the ID is not in the [1, 16**16] range, or if not a valid string
    """

    try:
        device_slug = IOTileDeviceSlug(id)
    except Exception:
        raise ArgumentError("Unable to recognize {} as a device id".format(id))

    return str(device_slug)
