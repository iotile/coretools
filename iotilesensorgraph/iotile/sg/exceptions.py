from iotile.core.exceptions import IOTileException


class StreamEmptyError(IOTileException):
    """Thrown when a stream walker is empty."""

    pass


class StorageFullError(IOTileException):
    """Thrown when more readings can not be stored because the storage area is full."""

    pass


class TooManyOutputsError(IOTileException):
    """Thrown when there are more outputs required for a node than it can support."""

    pass


class TooManyInputsError(IOTileException):
    """Thrown when there are more inputs to a node than its maximum number of inputs."""

    pass
