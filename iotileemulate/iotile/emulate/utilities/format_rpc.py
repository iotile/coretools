"""Utility function to pretty print an rpc call and response."""

from binascii import hexlify
from ..constants import rpc_name

def format_rpc(data):
    """Format an RPC call and response.

    Args:
        data (tuple): A tuple containing the address, rpc_id, argument and
            response payloads and any error code.

    Returns:
        str: The formated RPC string.
    """

    address, rpc_id, args, resp, _status = data

    name = rpc_name(rpc_id)

    if isinstance(args, (bytes, bytearray)):
        arg_str = hexlify(args)
    else:
        arg_str = repr(args)

    if isinstance(resp, (bytes, bytearray)):
        resp_str = hexlify(resp)
    else:
        resp_str = repr(resp)

    #FIXME: Check and print status as well
    return "%s called on address %d, payload=%s, response=%s" % (name, address, arg_str, resp_str)
