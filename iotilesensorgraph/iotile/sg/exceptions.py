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


class NodeConnectionError(IOTileException):
    """Thrown when a node is created with its inputs unconnected.

    Nodes that depend on the output of other nodes need to be created after
    those nodes have already been created.  If a node is created and its inputs
    do not refer either to global inputs or to other nodes that have already
    been created, this exception is thrown.
    """

    pass


class ProcessingFunctionError(IOTileException):
    """Thrown when a processing function for a node is invalid.

    This can either be thrown during an attempt to execute the processing
    function if it cannot be found or was not set correctly.  It can also
    be thrown during serializing a sensor graph for embedding into an IOTile
    Device if the procesing function is not available on the embedded device.
    """

    pass
