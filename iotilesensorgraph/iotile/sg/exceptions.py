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


class SensorGraphSyntaxError(IOTileException):
    """Thrown when there is an error parsing a sensor graph description file.

    The parameters line and column will indicate where the error occured and
    other paremeters will give more specific information about what was expected.
    """

    pass


class SensorGraphSemanticError(IOTileException):
    """Thrown when a syntactically valid statement occurs in a context that is not valid.

    Not all statements can appear in all scopes.  This exception indicates a semantic error
    where a statement appears in a scope that does not allow it.
    """

    pass


class UnresolvedIdentifierError(IOTileException):
    """Thrown when an identifier is asked for but cannot be found.

    The name of the identifier is given in the parameters.  This exception will
    also be thrown if an identifier is found but resolves to an object of an incorrect
    type.  For example, if you are asking for a DataStream but the identifier names
    a SlotIdentifier.
    """

    pass
