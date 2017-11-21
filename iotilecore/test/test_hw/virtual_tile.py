"""Virtual Tile for testing TileBasedVirtualDevice."""

from iotile.core.hw.virtual import VirtualTile, tile_rpc
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotile.core.utilities.typedargs import param, return_type, context

@context("TestProxy")
class TestTileProxy(TileBusProxyObject):
    @param("arg_1", "integer")
    @param("arg_2", "integer")
    @return_type("integer")
    def add(self, arg_1, arg_2):
        """Add two numbers."""
        res, = self.rpc(0x80, 0x00, arg_1, arg_2, arg_format="LL", result_format="L")
        return res

    @return_type("integer")
    def count(self):
        """Add two numbers."""
        res, = self.rpc(0x80, 0x01, result_format="L")
        return res

    @classmethod
    def ModuleName(cls):
        return 'test01'


class TestTile(VirtualTile):
    def __init__(self, address, _args, device=None):
        super(TestTile, self).__init__(address, 'test01')
        self._counter = 0

        # Test worker creation
        self.create_worker(self._increment_counter, 1.0)

    def _increment_counter(self):
        self._counter += 1

    @tile_rpc(0x8000, "LL", "L")
    def add(self, arg_1, arg_2):
        """Add arg_1 and arg_2."""

        return [arg_1 + arg_2]

    @tile_rpc(0x8001, "", "L")
    def count(self):
        """Return the current counter value."""

        return [self._counter]
