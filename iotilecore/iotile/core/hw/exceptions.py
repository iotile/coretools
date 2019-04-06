# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# exceptions.py

import iotile.core.exceptions

class DeviceAdapterError(iotile.core.exceptions.HardwareError):
    """A protocol or communication error occurred during an operation.

    This exception indicates that a DeviceAdapter was not able to perform
    the desired operation because of a communication-type error.

    Args:
        conn_id (int): The connection id that the error occurred on.  If the
            error was not associated with a connection then this will be None.
        operation (str): A descriptive name of the operation that was being
            performed.
        reason (str): A helpful string about what the issue was.
    """

    def __init__(self, conn_id, operation, reason):
        super(DeviceAdapterError, self).__init__("Operation {} on conn {} failed because {}".
                                                 format(operation, conn_id, reason),
                                                 reason=reason, operation=operation,
                                                 conn_id=conn_id)

        self.reason = reason


class DeviceServerError(iotile.core.exceptions.HardwareError):
    """The device server rejected your request because it was invalid.

    This exception indicates that the request was never forwarded to the
    underlying device adapter but rather reject by the DeviceServer
    implementation itself because it was disallowed or invalid.

    For example, if you are trying to access a device for which you
    do not have an active connection.  Or disconnecting a device that
    you did not connect.

    The client_id, reason and connection_string are available as
    properties on the exception instance to assist with converting
    the error into a message to send back to the client.

    Args:
        client_id (str): The client id that requested the invalid
            operation.
        conn_str (str): The connection string for the device in question.
        operation (str): A descriptive name of the operation that was
            requested.
        reason (str): A helpful string about what the issue was.
    """

    def __init__(self, client_id, conn_str, operation, reason):
        super(DeviceServerError, self).__init__("Operation {} for client {} on device {} failed because {}".
                                                format(operation, client_id, conn_str, reason),
                                                reason=reason, operation=operation,
                                                conn_string=conn_str, client_id=client_id)

        self.reason = reason
        self.client_id = client_id
        self.connection_string = conn_str


class RPCError(iotile.core.exceptions.HardwareError):
    pass


class RPCNotFoundError(RPCError):
    """Exception thrown when an RPC is not found."""
    pass


class RPCInvalidArgumentsError(RPCError):
    """Exception thrown when an RPC with a fixed parameter format has invalid arguments."""
    pass


class RPCInvalidReturnValueError(RPCError):
    """Exception thrown when the return value of an RPC does not conform to its known format."""

    def __init__(self, address, rpc_id, format_code, response, **kwargs):
        super(RPCInvalidReturnValueError, self).__init__("Invalid return value from Tile %d, RPC 0x%04x, "
                                                         "expected format %s, got %d bytes"
                                                         % (address, rpc_id, format_code, len(response)), **kwargs)

        self.address = address
        self.rpc_id = rpc_id
        self.format_code = format_code
        self.response = response


class RPCInvalidIDError(RPCError):
    """Exception thrown when an RPC is created with an invalid RPC id."""
    pass


class TileNotFoundError(RPCError):
    """Exception thrown when an RPC is sent to a tile that does not exist."""
    pass


class RPCErrorCode(RPCError):
    """Exception thrown from an RPC implementation to set the status code."""

    def __init__(self, status_code):
        super(RPCErrorCode, self).__init__("RPC returned application defined status code %d" % status_code,
                                           code=status_code)


class AsynchronousRPCResponse(RPCError):
    """Exception thrown from an RPC implementation when it will return asynchronously.

    This exception is never returned from a call to self.rpc or self.rpc_v2
    inside of a TileBus proxy, it is just used internally to know when to
    block that call and wait for the actual RPC response to come through a
    callback.
    """

    def __init__(self):
        super(AsynchronousRPCResponse, self).__init__("RPC handler elected to return asynchronously")


class BusyRPCResponse(RPCError):
    """Exception thrown from an RPC implementation when a tile is busy handling asynchronous request"""

    def __init__(self, msg="Tile tile is busy"):
        super(BusyRPCResponse, self).__init__(msg)


VALID_RPC_EXCEPTIONS = (BusyRPCResponse, TileNotFoundError, RPCErrorCode, RPCInvalidIDError, RPCNotFoundError)


class UnknownModuleTypeError(iotile.core.exceptions.TypeSystemError):
    pass
