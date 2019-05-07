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


class DevicePushError(iotile.core.exceptions.HardwareError):
    """Base class for errors related to virtual devices pushing to clients.

    These errors can be thrown when a virtual device attempts to stream
    reports and the report streaming process fails or when it attempts to
    trace data.

    The details of the failure reason are contained in the message.
    """


class InterfaceClosedError(DevicePushError):
    """An asynchronous device push failed because the required interface was closed.

    This is a typical error that is raised when, for example, a device
    attempts to stream a report without the streaming interface being opened.
    """

    def __init__(self, interface):
        super(InterfaceClosedError, self).__init__("Cannot push data to client because the {} interface is not open".
                                                   format(interface), interface=interface)


class RPCError(iotile.core.exceptions.HardwareError):
    """Base class for all RPC related errors.

    Instances of this class should not be raised directly but it
    just provides a standard base for checking against the specific
    kinds of errors that can happen while running an RPC.
    """


class RPCNotFoundError(RPCError):
    """The RPC id was not found on the tile.

    This exception always indicates that the tile itself was responding
    correctly and was able to handle RPCs.  It just did not find an RPC
    matching the RPC id that was specified.
    """


class RPCInvalidArgumentsError(RPCError):
    """An RPC with a fixed parameter format was given invalid arguments."""


class RPCInvalidReturnValueError(RPCError):
    """The return value of an RPC does not conform to its known format.

    When the RPC is implemented in python in a virtual tile, this may also be
    thrown if invalid python objects are returned that cannot be packed for
    transport.
    """

    def __init__(self, address, rpc_id, format_code, response, **kwargs):
        if response is None:
            resp_len = 0
        else:
            resp_len = len(response)

        super(RPCInvalidReturnValueError, self).__init__("Invalid return value from Tile %s, RPC 0x%04x, "
                                                         "expected format %s, got %d bytes"
                                                         % (address, rpc_id, format_code, resp_len), **kwargs)

        self.address = address
        self.rpc_id = rpc_id
        self.format_code = format_code
        self.response = response


class RPCInvalidIDError(RPCError):
    """The RPC ID given is an invalid type or size to specify an RPC."""


class TileNotFoundError(RPCError):
    """An RPC was sent to a tile that does not exist.

    This is distinct from :class:`RPCNotFoundError`, which means that the
    destination address was correct and that tile responded positively that
    the RPC could not be found.  This error means that no response was
    received from the tile at all.
    """


class RPCErrorCode(RPCError):
    """The RPC chose to return an implementation defined error code.

    Use of this exception is discouraged since RPCs implementations should
    return their error codes inside the response payload along with any data
    that they may want to return.  However there are certain cases where RPC
    implementation need a way to indicate an error while returning no response
    and raising this RPCErrorCode exception is the way to do it.

    Args:
        status_code (int): The error code that should be raised to the caller.
    """

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
    """The Tile was busy and could not handle an RPC right now.

    This exception is rarely exposed directly to a user.  Internally, it can be
    the case that an RPC cannot be executed at a specific moment because a
    long-running asynchronous RPC is in progress.  In that case, the
    :meth:`TileBusProxyObject.rpc` method automatically retries the RPC later.
    If multiple attempts to retry the RPC fail, this exception will ultimately
    be raised to the user.
    """

    def __init__(self, msg="Tile tile is busy"):
        super(BusyRPCResponse, self).__init__(msg)


VALID_RPC_EXCEPTIONS = (BusyRPCResponse, TileNotFoundError, RPCErrorCode, RPCInvalidIDError, RPCNotFoundError)


class UnknownModuleTypeError(iotile.core.exceptions.TypeSystemError):
    """A suitable proxy could not be found for a given tile.

    This means that the name returned by the tile's get_info RPC was not found
    in our local database of known tile names so a suitable proxy class could
    not be instantiated.  Typically this means that you need to find and
    install the support package for the tile that you wish to use.
    """
