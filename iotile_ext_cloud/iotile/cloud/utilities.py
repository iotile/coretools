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

def device_id_to_slug(id):
    """ Converts a device id into a correct device slug.

    Args:
        id (long) : A device id
    Returns:
        str: The device slug in the d--XXXX-XXXX-XXXX-XXXX format
    Raises:
        ArgumentError: if the ID is not in the [1, 16**16] range, or if it is not an int
    """
    if isinstance(id,int):
        id = long(id)
    elif not isinstance(id,long):
        raise ArgumentError("Id is not a number")
    if (id <= 0 or id > pow(16,16)):
        raise ArgumentError("Id not in the correct range")

    id = hex(id)[2:-1] # get rid of the 0x and the trailing L

    id = id.zfill(16).lower()   # pad to 16 chars and convert to lowercase

    chunks = [id[i:i+4] for i in range(0, len(id), 4)] # get 4 strings of 4 chars

    return 'd--' + '-'.join(chunks)
