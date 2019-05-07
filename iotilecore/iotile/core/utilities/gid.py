from iotile.core.exceptions import ArgumentError

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
