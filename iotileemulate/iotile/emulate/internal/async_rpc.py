import binascii
import struct
from iotile.core.hw.virtual.common_types import RPCInvalidIDError, unpack_rpc_payload, pack_rpc_payload, RPCInvalidArgumentsError, RPCInvalidReturnValueError


def async_rpc(address, rpc_id, arg_format, resp_format=None):
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
        async def _rpc_executor(self, payload):
            try:
                args = unpack_rpc_payload(arg_format, payload)
            except struct.error as exc:
                raise RPCInvalidArgumentsError(str(exc), arg_format=arg_format, payload=binascii.hexlify(payload))

            resp = await func(self, *args)

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


def async_tile_rpc(rpc_id, arg_format, resp_format=None):
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

    return async_rpc(None, rpc_id, arg_format, resp_format)
