
def uuid_to_connection_string(uuid):
    """Get the connection string from the uuid of a device.

    Args:
        uuid (int): The unique identifier of the device

    Returns:
        connection_string (str): The connection string designing the same device as the given uuid
    """

    return str(uuid)


def connection_string_to_uuid(connection_string):
    """Get the uuid of a device from a connection string.

    Args:
        connection_string (str): The connection string (probably received from external script)

    Returns:
        uuid (int): The unique identifier of the device
    """

    return int(connection_string)
