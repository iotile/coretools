"""Common utility functions used across iotile.cloud packages."""

from iotile.core.exceptions import ArgumentError

from calendar import timegm

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

def get_timestamp(utcdate):
    """ retrieves the UNIX UTC timestamp from formatted text ( 06 Sep 2017 16:50:46 )"""
    months = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
              'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    utcdate = utcdate.split(' ')
    year, day = utcdate[2], utcdate[0]
    month = months[utcdate[1]]
    utcdate = utcdate[-1].split(':')
    hour, m, sec = utcdate[0], utcdate[1], utcdate[2]
    return(timegm(list(map(lambda x: int(x),(year,month,day,hour,m,sec)))))
