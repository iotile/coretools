from iotile.core.hw.proxy.proxy import TileBusProxyObject
from typedargs.annotate import context


@context("SimpleProxy")
class SimpleProxyObject(TileBusProxyObject):
    """A simply proxy object to correspond with SimpleVirtualDevice
    """

    @classmethod
    def ModuleName(cls):
        return 'Simple'
