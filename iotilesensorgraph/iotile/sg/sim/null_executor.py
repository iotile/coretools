"""A simple RPC executor that always responds with zeros."""

import struct
from .executor import RPCExecutor


class NullRPCExecutor(RPCExecutor):
    """A mock RPCExecutor that always returns 0."""

    def _call_rpc(self, address, rpc_id, payload):
        """Call an RPC with the given information and return its response.

        Must raise a hardware error of the appropriate kind if the RPC
        can not be executed correctly.  Otherwise it should return the binary
        response payload received from the RPC.

        Args:
            address (int): The address of the tile we want to call the RPC
                on
            rpc_id (int): The id of the RPC that we want to call
            payload (bytes, bytearray): The data that we want to send as the payload
        """

        return struct.pack("<L", 0)
