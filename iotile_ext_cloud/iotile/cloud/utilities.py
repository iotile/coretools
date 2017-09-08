"""Common utility functions used across iotile.cloud packages."""

from iotile.core.exceptions import ArgumentError

from string import hexdigits

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
        id (str) : A device id in either of the following formats :
            XXXX XXXX XXXX XXXX
            XXXXXXXXXXXXXXXX
            0xXXXXXXXXXXXXXXXX
    Returns:
        str: The device slug in the d--XXXX-XXXX-XXXX-XXXX format
    Raises:
        ArgumentError: if the ID is more than 16 chars or if it contains characters outside 0123456789ABCDEF
    """

    if not isinstance(id, (str, unicode)):
        raise ArgumentError("Invalid device id that is not a string", id=id)

    id = id.replace(' ','') # get rid of the spaces

    if (id.startswith('0x')):
        id = id[2:] # remove 0x identifier

    id = id.zfill(16).lower()   # pad to 16 chars and convert to uppercase
    if (not set(id) <= set(hexdigits)):
        raise ArgumentError("ID cannot contain non hexadecimal characters !")
    if (len(id) > 16):
        raise ArgumentError("ID cannot be more than 16 chars !")

    chunks = [id[i:i+4] for i in range(0, len(id), 4)] # get 4 strings of 4 chars

    return 'd--' + '-'.join(chunks)
