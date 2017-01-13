"""Mock IOTile device class for testing other components interactions with IOTile devices
"""

import struct
import functools
import inspect
from iotile.core.exceptions import *

class RPCNotFoundError(IOTileException):
    """Exception thrown when an RPC is not found
    """
    pass

class RPCInvalidArgumentsError(IOTileException):
    """Exception thrown when an RPC with a fixed parameter format has invalid arguments
    """
    pass

class RPCInvalidReturnValueError(IOTileException):
    """Exception thrown when the return value of an RPC does not conform to its known format
    """
    pass

class RPCInvalidIDError(IOTileException):
    """Exception thrown when an RPC is created with an invalid RPC id
    """
    pass

class TileNotFoundError(IOTileException):
    """Exception thrown when an RPC is sent to a tile that does not exist
    """
    pass

def rpc(address, rpc_id, arg_format, resp_format=None):
    """Decorator to denote that a function implements an RPC at an address

    The underlying function should be a member function that will take
    individual parameters after the RPC payload has been decoded according
    to arg_format

    Args:
        address (int): The address of the mock tile this RPC is for
        rpc_id (int): The number of the RPC
        arg_format (string): a struct format code (without the <) for the
            parameter format for this RPC
        resp_format (string): an optional format code (without the <) for
            the response format for this RPC
    """

    if rpc_id < 0 or rpc_id > 0xFFFF:
        raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))


    def _rpc_wrapper(func):
        def _rpc_executor(self, payload):
            args = struct.unpack("<{}".format(arg_format), payload)

            resp = func(self, *args)
            if resp_format is not None:
                try:
                    return struct.pack("<{}".format(resp_format), *resp)
                except struct.error as exc:
                    raise RPCInvalidReturnValueError(str(exc))

            return resp

        _rpc_executor.rpc_id = rpc_id
        _rpc_executor.rpc_addr = address
        _rpc_executor.is_rpc = True
        return _rpc_executor

    return _rpc_wrapper

class VirtualIOTileDevice(object):
    """A Virtual IOTile device that can be interacted with as if it were a real one

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        name (string): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    def __init__(self, iotile_id, name):
        self._rpc_handlers = {}
        self.tiles = set()
        self.name = name
        self.iotile_id = iotile_id
        self.pending_data = False
        self.reports = []
        self.script = bytearray()

        #Iterate through all of our member functions and see the ones that are
        #RPCS and add them to the RPC handler table
        for name, value in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(value, 'is_rpc'):
                self.register_rpc(value.rpc_addr, value.rpc_id, value)

    def register_rpc(self, address, rpc_id, func):
        """Register an RPC handler with the given info

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            func (callable): The function that should be called to handle the
                RPC.  func is called as func(payload) and must return a single
                string object of up to 20 bytes with its response
        """

        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))
        
        self.tiles.add(address)

        code = (address << 8) | rpc_id
        self._rpc_handlers[code] = func

    def call_rpc(self, address, rpc_id, payload=""):
        """Call an RPC by its address and ID

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (string): A byte string of payload parameters up to 20 bytes

        Returns:
            string: The response payload from the RPC
        """
        if rpc_id < 0 or rpc_id > 0xFFFF:
            raise RPCInvalidIDError("Invalid RPC ID: {}".format(rpc_id))

        if address not in self.tiles:
            raise TileNotFoundError("Unknown tile address, no registered handler", address=address)

        code = (address << 8) | rpc_id
        if code not in self._rpc_handlers:
            raise RPCNotFoundError("address: {}, rpc_id: {}".format(address, rpc_id))

        return self._rpc_handlers[code](payload)

    def open_rpc_interface(self):
        """Called when someone opens an RPC interface to the device
        """

        pass

    def close_rpc_interface(self):
        """Called when someone closes an RPC interface to the device
        """

        pass

    def open_script_interface(self):
        """Called when someone opens a script interface on this device
        """

        pass

    def open_streaming_interface(self):
        """Called when someone opens a streaming interface to the device

        Returns:
            list: A list of IOTileReport objects that should be sent out
                the streaming interface.
        """

        return self.reports

    def close_streaming_interface(self):
        """Called when someone closes the streaming interface to the device
        """

        pass

    def push_script_chunk(self, chunk):
        """Called when someone pushes a new bit of a TRUB script to this device

        Args:
            chunk (str): a buffer with the next bit of script to append
        """

        self.script += bytearray(chunk)
