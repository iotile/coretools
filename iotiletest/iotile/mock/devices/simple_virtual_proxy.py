from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotile.core.utilities.typedargs.annotate import annotated,param,return_type, context


@context("SimpleProxy")
class SimpleProxyObject(TileBusProxyObject):
    """A simply proxy object to correspond with SimpleVirtualDevice
    """

    @classmethod
    def ModuleName(cls):
        return 'Simple'
