"""Virtual Tile for testing proxy matching."""

from iotile.core.hw.virtual import VirtualTile
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotile.core.utilities.typedargs import context

@context("TestProxyMatch")
class TestProxyMatch(TileBusProxyObject):
    """ TestProxyMatch is used to check the proxy matching feature.
        Note: if you are going to rename it,
        it must have the same name as another proxy(check virtual_tile.py)"""
    @classmethod
    def ModuleName(cls):
        return 'pmtest'


class SimpleTestTile(VirtualTile):
    def __init__(self, address, _args, device=None):
        super(SimpleTestTile, self).__init__(address, 'pmtest')
