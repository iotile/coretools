# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# exceptions.py

import iotile.core.exceptions


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
