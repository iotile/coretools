"""A simple RPC executor that always responds with zeros."""

import struct
from .executor import RPCExecutor
from iotile.core.hw.hwmanager import HardwareManager


class SemihostedRPCExecutor(RPCExecutor):
    """An RPC executor that runs RPCs on an IOTile device.

    This is used for "semihosting" a sensor graph where the SG engine
    runs on your computer but all RPCs are executed on a separete
    IOTile device.

    Semihosting is not 100% the same as running the SensorGraph on the
    device itself because:

    1. system inputs and inputs are currently not forwarded from the
       device to the computer so you cannot respond to events from tiles.
       (This will be addressed in the future)
    2. config variables set in the sensor graph are currently not set
       in the device, which means tiles that have required configurations need to
       be manually configured before semihosting a sensor graph.
       (This will be addressed in the future)

    Args:
        port (str): The port we should use to create a HardwareManager instance
            conected to our device.
        device_id (int): The device id we should connect to.
    """

    def __init__(self, port, device_id):
        self.hw = HardwareManager(port=port)
        self.hw.connect(device_id)

        super(SemihostedRPCExecutor, self).__init__()

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

        # FIXME: Set a timeout of 1.1 seconds to make sure we fail if the device hangs but
        #        this should be long enough to accomodate any actual RPCs we need to send.

        status, response = self.hw.stream.send_rpc(address, rpc_id >> 8, rpc_id & 0xFF, payload, timeout=1.1)
        return response
