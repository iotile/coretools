"""Common utility functions used across iotile.cloud packages."""

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

    if not slug.startswith("d--"):
        raise ArgumentError("Invalid device slug without d-- prefix", slug=slug)

    short = slug[3:]
    short = short.replace('-', '')

    try:
        return int(short, 16)
    except ValueError as exc:
        raise ArgumentError("Invalid device slug with non-numeric components", error_mesage=str(exc), slug=slug)
