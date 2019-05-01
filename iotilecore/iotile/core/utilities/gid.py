import re
from iotile.core.exceptions import *

# Generate a 0000-0000-0000-0001 given an integer
int64gid = lambda n: '-'.join(['{:04x}'.format(n >> (i << 4) & 0xFFFF) for i in range(0, 4)[::-1]])


def uuid_to_slug(uuid):
    """
    Return IOTile Cloud compatible Device Slug

    :param uuid: UUID
    :return: string in the form of d--0000-0000-0000-0001
    """
    if not isinstance(uuid, int):
        raise ArgumentError("Invalid id that is not an integer", id=uuid)

    if uuid < 0 or uuid > 0x7fffffff:
        # For now, limiting support to a signed integer (which on some platforms, can be 32bits)
        raise ArgumentError("Integer should be a positive number and smaller than 0x7fffffff", id=uuid)

    return '--'.join(['d', int64gid(uuid)])


def parse_uuid(uuidinput, prefix=None):
    """
    Parses and decodes an input as a uuid in various forms

        uuidinput:
            Input that can be a string or integer.
            Strings can be in hex prefixed as 0x
            Strings can be an integer not prefixed with 0x
            Strings can be as a uuid in the form of
                '0000-0000-0000-0000'
                'd--0000-0000-0000-0000'
                'd--0000-0000-0000'
                'd--0000-0000'
                'd--0000'

        prefix (str): If present, indicates the prefix to prepend
            to the slug output.

    Returns:
        uuid (int): UUID as an integer
        slug (str): UUID in format of 'XXXX-XXXX-XXXX-XXXX'
    """
    uuid = None
    slug = None

    def i2slug(value, prefix=None):
        if value is None:
            raise ArgumentError("Input is required")
        if uuid < 0 or uuid > 0x7fffffff:
            raise ArgumentError("Integer should be a positive number and smaller than 0x7fffffff", id=uuid)

        out = int64gid(value)

        if prefix is not None:
            out = prefix + '--' + out

        return out

    if uuidinput is None:
        raise ArgumentError("Input is required")

    if type(uuidinput) is int:
        uuid = uuidinput
        slug = i2slug(uuid, prefix)

    elif type(uuidinput) is str:
        hex_str_re = "^(0x[0-9a-fA-F]{1,12})$"
        int_str_re = "^([0-9]{1,15})$"
        slug1_re = "^0000-([0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4})$"
        slug2_re = "^d--0000-([0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4})$"
        slug3_re = "^d--([0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4})$"
        slug4_re = "^d--([0-9a-fA-F]{4}-[0-9a-fA-F]{4})$"
        slug5_re = "^d--([0-9a-fA-F]{4})$"
        uuidinput = uuidinput.strip()
        hex_result   = re.match(hex_str_re, uuidinput)
        int_result   = re.match(int_str_re, uuidinput)
        slug1_result = re.match(slug1_re,   uuidinput)
        slug2_result = re.match(slug2_re,   uuidinput)
        slug3_result = re.match(slug3_re,   uuidinput)
        slug4_result = re.match(slug4_re,   uuidinput)
        slug5_result = re.match(slug5_re,   uuidinput)
        if hex_result or int_result:
            uuid = int(uuidinput, 0)
        elif slug1_result:
            uuid = int(re.sub('-','',slug1_result.group(1)), 16)
        elif slug2_result:
            uuid = int(re.sub('-','',slug2_result.group(1)), 16)
        elif slug3_result:
            uuid = int(re.sub('-','',slug3_result.group(1)), 16)
        elif slug4_result:
            uuid = int(re.sub('-','',slug4_result.group(1)), 16)
        elif slug5_result:
            uuid = int(re.sub('-','',slug5_result.group(1)), 16)
        slug = i2slug(uuid, prefix)

    return uuid, slug

def parse_uuid2int(uuidinput):
    u, s = parse_uuid(uuidinput)
    return u

def parse_uuid2slug(uuidinput, prefix=None):
    u, s = parse_uuid(uuidinput, prefix)
    return s
