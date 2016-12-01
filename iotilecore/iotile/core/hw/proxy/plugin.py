from iotile.core.hw.commands import RPCCommand
from iotile.core.hw.exceptions import *
from time import sleep
import proxy

class TileBusProxyPlugin (object):
	"""
	Proxy plugin objects are mixin style classes that add functionality modules to proxy objects
	"""

	def __init__(self, parent):
		if not isinstance(parent, proxy.TileBusProxyObject):
			raise ArgumentError("Attempting to initialize a TileBusProxyPlugin with an invalid parent object", parent=parent)

		self._proxy = parent

	def rpc(self, feature, cmd, *args, **kw):
		return self._proxy.rpc(feature, cmd, *args, **kw)
