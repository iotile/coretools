from iotile.core.hw.proxy.proxy import TileBusProxyObject

class ARMProxy(TileBusProxyObject):
    """Provide access to ARM tile functionality"""

    @classmethod
    def ModuleName(cls):
        return 'progts'
