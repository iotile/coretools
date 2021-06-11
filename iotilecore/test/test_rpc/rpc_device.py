"""Virtual Tile for testing TileBasedVirtualDevice."""

from iotile.core.hw.virtual import VirtualTile, tile_rpc


class TestTile(VirtualTile):
    def __init__(self, address, _args, device=None):
        super(TestTile, self).__init__(address, 'test42')

    @tile_rpc(0x0000, "LL", "L")
    def add(self, arg_1, arg_2):
        """Add arg_1 and arg_2."""
        return [arg_1 + arg_2]

    @tile_rpc(0x1111, "", "")
    def null_rpc(self):
        pass

    @tile_rpc(0x8091, "BB12s", "L")
    def invalid_rpc_args_length_test(self, a, b, c):
        return [1]


    @tile_rpc(0xaaaa, "L", "")
    def invalid_rpc_args_empty_pass_in(self, a):
        return []
