from iotile.core.exceptions import IOTileException


class StreamEmptyError(IOTileException):
    """Thrown when a stream walker is empty."""

    pass
