"""Virtual Tile for testing proxy collision."""

from iotile.core.hw.virtual import VirtualTile
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotile.core.utilities.typedargs import context

@context("TestProxy")
class TestTileProxy(TileBusProxyObject):
    """ TestTileProxy is used to check if there is no collision between proxies.
        Note: if you are going to rename it,
        it must have the same name as another proxy(check virtual_tile.py)"""
    @classmethod
    def ModuleName(cls):
        return 'test02'


class SimpleTestTile(VirtualTile):
    def __init__(self, address, _args, device=None):
        super(SimpleTestTile, self).__init__(address, 'test02')
