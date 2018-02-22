from typedargs.exceptions import ArgumentError
from .proxy import TileBusProxyObject

class TileBusProxyPlugin(object):
    """
    Proxy plugin objects are mixin style classes that add functionality modules to proxy objects
    """

    def __init__(self, parent):
        if not isinstance(parent, TileBusProxyObject):
            raise ArgumentError("Attempting to initialize a TileBusProxyPlugin with an invalid parent object", parent=parent)

        self._proxy = parent

    def rpc(self, feature, cmd, *args, **kw):
        return self._proxy.rpc(feature, cmd, *args, **kw)
