from iotile.core.exceptions import IOTileException


class StreamEmptyError(IOTileException):
    """Thrown when a stream walker is empty."""

    pass


class StorageFullError(IOTileException):
    """Thrown when more readings can not be stored because the storage area is full."""

    pass
