"""Common utility functions used across iotile.cloud packages."""

from iotile_cloud.utils.gid import IOTileDeviceSlug, IOTileFleetSlug
from iotile.core.exceptions import ArgumentError
from past.builtins import basestring

def device_slug_to_id(slug):
    """Convert a d-- device slug to an integer.

    Args:
        slug (str): A slug in the format d--XXXX-XXXX-XXXX-XXXX

    Returns:
        int: The device id as an integer

    Raises:
        ArgumentError: if there is a malformed slug
    """

    if not isinstance(slug, basestring):
        raise ArgumentError("Invalid device slug that is not a string", slug=slug)

    try:
        device_slug = IOTileDeviceSlug(slug, allow_64bits=False)
    except ValueError:
        raise ArgumentError("Unable to recognize {} as a device id".format(slug))

    return device_slug.get_id()


def device_id_to_slug(id):
    """ Converts a device id into a correct device slug.

    Args:
        id (long) : A device id
        id (string) : A device slug in the form of XXXX, XXXX-XXXX-XXXX, d--XXXX, d--XXXX-XXXX-XXXX-XXXX
    Returns:
        str: The device slug in the d--XXXX-XXXX-XXXX-XXXX format
    Raises:
        ArgumentError: if the ID is not in the [1, 16**12] range, or if not a valid string
    """

    try:
        device_slug = IOTileDeviceSlug(id, allow_64bits=False)
    except ValueError:
        raise ArgumentError("Unable to recognize {} as a device id".format(id))

    return str(device_slug)


def fleet_id_to_slug(id):
    """ Converts a fleet id into a correct fleet slug.

    Args:
        id (long) : A fleet id
        id (string) : A device slug in the form of XXXX, XXXX-XXXX-XXXX, g--XXXX, g--XXXX-XXXX-XXXX
    Returns:
        str: The device slug in the g--XXXX-XXXX-XXX format
    Raises:
        ArgumentError: if the ID is not in the [1, 16**12] range, or if not a valid string
    """

    try:
        fleet_slug = IOTileFleetSlug(id)
    except ValueError:
        raise ArgumentError("Unable to recognize {} as a fleet id".format(id))

    return str(fleet_slug)
