"""A simply proxy class for controlling the DemoEmulatedTile."""

from typedargs.annotate import docannotate, context
from iotile.core.hw.proxy import TileBusProxyObject
from iotile.core.exceptions import ArgumentError

@context("DemoTile")
class DemoTileProxy(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'emudmo'

    @docannotate
    def trace_data(self, byte_count):
        """Trigger the tracing of data.

        This method lets you test receiving traced data out of a device. It
        will synchronously wait unitl the given number of bytes have been
        received.

        Args:
            byte_count (int): The number of bytes that should be traced.

        Returns:
            int: The number of bytes that were successfully received.
        """

        self.rpc_v2(0x8003, "L", "", byte_count)

        data = self._hwmanager.wait_trace(byte_count, timeout=((.15 * ((byte_count // 20) + 1)) + .5))
        return len(data)

    @docannotate
    def fetch_counter(self):
        """Fetch and increment the tile's counter value.

        This method returns the current counter and causes the tile
        to increment it by one.

        Returns:
            int: The current counter value before incrementing.
        """

        data, = self.rpc_v2(0x8002, "", "L")
        return data

    @docannotate
    def echo(self, value, method="sync"):
        """Echo a number.

        The echo RPC on the emulated tile are implemented using
        three different methods that you can choose by passing
        method=(sync|async|coroutine)

        The result of all three methods is the same from the caller's
        point of view.

        Args:
            value (int): The value to echo
            method (str): The specific RPC implementation to use.  This
                may be sync, async or coroutine.

        Returns:
            int: The echoed value.
        """

        rpc_map = {
            'sync': 0x8001,
            'async': 0x8000,
            'coroutine': 0x8004
        }

        rpc_id = rpc_map.get(method)
        if rpc_id is None:
            raise ArgumentError("Unknown method: %s" % method, known_methods=list(rpc_map))

        response, = self.rpc_v2(rpc_id, "L", "L", value)
        return response
