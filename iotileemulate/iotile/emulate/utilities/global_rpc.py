"""A wrapper around tile_rpc that can take an RPCDeclaration."""

from iotile.core.hw.virtual import tile_rpc
from ..constants.rpcs import RPCDeclaration

def global_rpc(declaration):
    """Decorate a method to mark it as implementing a globally declared RPC.

    Internally this just calls tile_rpc with the information from the RPCDeclaration.

    Args:
        declaration (RPCDeclaration): A global RPC declaration.

    Returns:
        decorator: A decorator that can be applied to a function or method.
    """

    if not isinstance(declaration, RPCDeclaration):
        raise TypeError("You can only use global RPCDeclaration objects with global_rpc, use tile_rpc for custom rpcs")

    return tile_rpc(declaration.rpc_id, declaration.arg_format, declaration.resp_format)
