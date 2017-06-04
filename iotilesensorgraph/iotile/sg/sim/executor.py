"""Base class for RPC executors.

RPC Executors are objects whose job is to send an RPC and interpret
the response as a sensor graph reading.

They can either run the RPC on an actual device or they can run it
locally in a simulated device or just mock the response as needed.
"""

import struct
from iotile.core.exceptions import InternalError, HardwareError


class RPCExecutor(object):
    """RPC Executors run RPCs on behalf of sensor graph."""

    def __init__(self):
        self.warning_channel = None
        self.mock_rpcs = {}

    def mock(self, slot, rpc_id, value):
        """Store a mock return value for an RPC

        Args:
            slot (SlotIdentifier): The slot we are mocking
            rpc_id (int): The rpc we are mocking
            value (int): The value that should be returned
                when the RPC is called.
        """

        address = slot.address

        if address not in self.mock_rpcs:
            self.mock_rpcs[address] = {}

        self.mock_rpcs[address][rpc_id] = value

    def warn(self, message):
        """Let the user of this RPCExecutor know about an issue.

        warn should be used when the RPC processed in a nonstandard way
        that typically indicates a misconfiguration or problem but did
        technically complete successfully.
        """

        if self.warning_channel is None:
            return

    def rpc(self, address, rpc_id):
        """Call an RPC and receive the result as an integer.

        If the RPC does not properly return a 32 bit integer, raise a warning
        unless it cannot be converted into an integer at all, in which case
        a HardwareError is thrown.

        Args:
            address (int): The address of the tile we want to call the RPC
                on
            rpc_id (int): The id of the RPC that we want to call

        Returns:
            int: The result of the RPC call.  If the rpc did not succeed
                an error is thrown instead.
        """

        # Always allow mocking an RPC to override whatever the defaul behavior is
        if address in self.mock_rpcs and rpc_id in self.mock_rpcs[address]:
            value = self.mock_rpcs[address][rpc_id]
            return value

        result = self._call_rpc(address, rpc_id, bytes())

        if len(result) != 4:
            self.warn(u"RPC 0x%X on address %d: response had invalid length %d not equal to 4" % (rpc_id, address, len(result)))

        if len(result) < 4:
            raise HardwareError("Response from RPC was not long enough to parse as an integer", rpc_id=rpc_id, address=address, response_length=len(result))

        if len(result) > 4:
            result = result[:4]

        res, = struct.unpack("<L", result)
        return res

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

        raise InternalError("RPCExecutor did not properly override _call_rpc")
