"""Custom exceptions for iotile-emulate."""

import struct
from iotile.core.exceptions import InternalError
from ..constants import pack_error

class RPCRuntimeError(Exception):
    """Exception that indicates an RPC had a runtime error.

    Runtime errors are application defined and are translated
    to a 16-bit or 32-bit return value containing the error
    code.

    Args:
        code (int): The error code that should be returned from
            the RPC.
        subsystem (int): The subsystem that the error code should
            be returned from.  This may only be passed if size=L
        size (str): Whether to return a 32-bit long-form error
            including subsystem or a 16-bit short-firm error.
            You may pass L or H.  The default is L, meaning
            32 bit errors.
    """

    def __init__(self, code, subsystem=None, size="L"):
        super(RPCRuntimeError, self).__init__()

        if size not in ("L", "H"):
            raise InternalError("Unknown size {} in RPCRuntimeError".format(size))

        if subsystem is not None and size == 'H':
            raise InternalError("You cannot combine size=H with a subsystem, subsystem={}".format(subsystem))

        if subsystem is not None:
            error = pack_error(subsystem, code)
        else:
            error = code

        self.code = error
        self.subsystem = subsystem
        self.packed_error = error

        print("Packed error: %r" % self.packed_error)
        self.binary_error = struct.pack("<{}".format(size), self.packed_error)
