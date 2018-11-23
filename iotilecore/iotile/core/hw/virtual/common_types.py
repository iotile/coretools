"""Shared decorators and exceptions used in virtual tiles and devices."""

import struct
import binascii
import inspect
from iotile.core.exceptions import IOTileException


class RPCNotFoundError(IOTileException):
    """Exception thrown when an RPC is not found."""
    pass


class RPCInvalidArgumentsError(IOTileException):
    """Exception thrown when an RPC with a fixed parameter format has invalid arguments."""
    pass


class RPCInvalidReturnValueError(IOTileException):
    """Exception thrown when the return value of an RPC does not conform to its known format."""
    pass


class RPCInvalidIDError(IOTileException):
    """Exception thrown when an RPC is created with an invalid RPC id."""
    pass


class TileNotFoundError(IOTileException):
    """Exception thrown when an RPC is sent to a tile that does not exist."""
    pass

class RPCErrorCode(IOTileException):
    """Exception thrown from an RPC implementation to set the status code."""

    def __init__(self, status_code):
        super(RPCErrorCode, self).__init__("RPC returned application defined status code %d" % status_code, code=status_code)


def _create_argcode(code, arg_bytes):
    if not code.endswith('V'):
        return "<" + code

    code = code[:-1]
    fixed_size = struct.calcsize("<" + code)
    var_size = len(arg_bytes) - fixed_size

    if var_size < 0:
        raise RPCInvalidArgumentsError("Argument was too small for variable size argument value", arg_format=code,
                                       minimum_size=fixed_size, actual_size=len(arg_bytes),
                                       payload=binascii.hexlify(arg_bytes))

    return "<" + code + "%ds" % var_size


def _create_respcode(code, resp):
    if not code.endswith('V'):
        return "<" + code

    code = code[:-1]

    final_length = len(resp[-1])
    fixed_size = struct.calcsize("<" + code)

    if fixed_size + final_length > 20:
        raise RPCInvalidReturnValueError("Variable length return value is too large for rpc response payload (20 bytes)",
                                         fixed_code=code, fixed_length=fixed_size, variable_length=final_length,
                                         variable_payload=binascii.hexlify(resp[-1]))
    return "<" + code + "%ds" % final_length


def pack_rpc_payload(arg_format, args):
    """Pack an RPC payload according to arg_format.

    Args:
        arg_format (str): a struct format code (without the <) for the
            parameter format for this RPC.  This format code may include the final
            character V, which means that it expects a variable length bytearray.
        args (list): A list of arguments to pack according to arg_format.

    Returns:
        bytes: The packed argument buffer.
    """

    code = _create_respcode(arg_format, args)
    return struct.pack(code, *args)


def unpack_rpc_payload(resp_format, payload):
    """Unpack an RPC payload according to resp_format.

    Args:
        resp_format (str): a struct format code (without the <) for the
            parameter format for this RPC.  This format code may include the final
            character V, which means that it expects a variable length bytearray.
        payload (bytes): The binary payload that should be unpacked.

    Returns:
        list: A list of the unpacked payload items.
    """

    code = _create_argcode(resp_format, payload)
    return struct.unpack(code, payload)


def rpc(address, rpc_id, arg_format, resp_format=None):
    """Decorator to denote that a function implements an RPC with the given ID and address.

    The underlying function should be a member function that will take
    individual parameters after the RPC payload has been decoded according
    to arg_format.

    Arguments to the function are decoded from the 20 byte RPC argument payload according
    to arg_format, which should be a format string that can be passed to struct.unpack.

    Similarly, the function being decorated should return an iterable of results that
    will be encoded into a 20 byte response buffer by struct.pack using resp_format as
    the format string.

    The RPC will respond as if it were implemented by a tile at address ``address`` and
    the 16-bit RPC id ``rpc_id``.

    Args:
        address (int): The address of the mock tile this RPC is for
        rpc_id (int): The number of the RPC
        arg_format (string): a struct format code (without the <) for the
            parameter format for this RPC.  This format code may include the final
            character V, which means that it expects a variable length bytearray.
        resp_format (string): an optional format code (without the <) for
            the response format for this RPC. This format code may include the final
            character V, which means that it expects a variable length bytearray.
    """

    if rpc_id < 0 or rpc_id > 0xFFFF:
        raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

    def _rpc_wrapper(func):
        def _rpc_executor(self, payload):
            try:
                args = unpack_rpc_payload(arg_format, payload)
            except struct.error as exc:
                raise RPCInvalidArgumentsError(str(exc), arg_format=arg_format, payload=binascii.hexlify(payload))

            resp = func(self, *args)

            if resp is None:
                resp = []

            if resp_format is not None:
                try:
                    return pack_rpc_payload(resp_format, resp)
                except struct.error as exc:
                    raise RPCInvalidReturnValueError(str(exc), resp_format=resp_format, resp=repr(resp))

            return resp

        _rpc_executor.rpc_id = rpc_id
        _rpc_executor.rpc_addr = address
        _rpc_executor.is_rpc = True
        return _rpc_executor

    return _rpc_wrapper


def tile_rpc(rpc_id, arg_format, resp_format=None):
    """Decorator to denote that a function implements an RPC with the given ID on a tile.

    The underlying function should be a member function that will take
    individual parameters after the RPC payload has been decoded according
    to arg_format.

    Arguments to the function are decoded from the 20 byte RPC argument payload according
    to arg_format, which should be a format string that can be passed to struct.unpack.

    Similarly, the function being decorated should return an iterable of results that
    will be encoded into a 20 byte response buffer by struct.pack using resp_format as
    the format string.

    The RPC will respond as if it were implemented by a tile at address ``address`` and
    the 16-bit RPC id ``rpc_id``.

    Args:
        rpc_id (int): The number of the RPC
        arg_format (string): a struct format code (without the <) for the
            parameter format for this RPC
        resp_format (string): an optional format code (without the <) for
            the response format for this RPC
    """

    return rpc(None, rpc_id, arg_format, resp_format)


class RPCDispatcher(object):
    """A simple dispatcher that can store and call RPCs."""

    def __init__(self, *args, **kwargs):
        super(RPCDispatcher, self).__init__(*args, **kwargs)
        self._rpcs = {}

        # Add any RPCs defined using decorators on this class
        for _name, value in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(value, 'is_rpc'):
                self.add_rpc(value.rpc_id, value)

    def add_rpc(self, rpc_id, func):
        """Add an RPC.

        Args:
            rpc_id (int): The ID of the RPC
            func (callable): The RPC implementation.
                The signature of callable should be callable(args) taking
                a bytes object with the argument and returning a bytes object
                with the response.
        """

        self._rpcs[rpc_id] = func

    def has_rpc(self, rpc_id):
        """Check if an RPC is defined.

        Args:
            rpc_id (int): The RPC to check

        Returns:
            bool: Whether it exists
        """

        return rpc_id in self._rpcs

    def call_rpc(self, rpc_id, payload=bytes()):
        """Call an RPC by its ID.

        Args:
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            str: The response payload from the RPC
        """
        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        if rpc_id not in self._rpcs:
            raise RPCNotFoundError("rpc_id: {}".format(rpc_id))

        return self._rpcs[rpc_id](payload)
