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


class ModuleBusyError(RPCError):
    def __init__(self, address, **kwargs):
        super(ModuleBusyError, self).__init__("Module responded that it was busy", address=address, **kwargs)


class UnsupportedCommandError(RPCError):
    def __init__(self, **kwargs):
        super(UnsupportedCommandError, self).__init__("Module did not support the specified command", **kwargs)


class ModuleNotFoundError(RPCError):
    def __init__(self, address, **kwargs):
        super(ModuleNotFoundError, self).__init__("Module was not found or did not respond", address=address, **kwargs)


class StreamNotConnectedError(RPCError):
    def __init__(self, **kwargs):
        super(StreamNotConnectedError, self).__init__("Stream was not connected to any MoMo devices", **kwargs)


class StreamOperationNotSupportedError(RPCError):
    def __init__(self, **kwargs):
        super(StreamOperationNotSupportedError, self).__init__("Underlying command stream does "
                                                               "not support the required operation", **kwargs)


class InvalidReturnValueError(RPCError):
    """Exception thrown when the return value of an RPC does not conform to its known format."""

    def __init__(self, address, rpc_id, format_code, response, **kwargs):
        super(InvalidReturnValueError, self).__init__("Invalid return value from Tile %d, RPC 0x%04x, "
                                                      "expected format %s, got %d bytes"
                                                      % (address, rpc_id, format_code, len(response)), **kwargs)

        self.address = address
        self.rpc_id = rpc_id
        self.format_code = format_code
        self.response = response


class UnknownModuleTypeError(iotile.core.exceptions.TypeSystemError):
    pass
