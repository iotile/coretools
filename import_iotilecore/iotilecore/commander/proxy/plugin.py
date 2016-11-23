from iotilecore.commander.commands import RPCCommand
from iotilecore.commander.exceptions import *
from time import sleep
import proxy

class TileBusProxyPlugin (object):
	"""
	Proxy plugin objects are mixin style classes that add functionality modules to proxy objects
	"""

	def __init__(self, parent):
		if not isinstance(parent, proxy.MIBProxyObject):
			raise ArgumentError("Attempting to initialize a TileBusProxyPlugin with an invalid parent object", parent=parent)

		self._proxy = parent

	def rpc(self, feature, cmd, *args, **kw):
		return self._proxy.rpc(feature, cmd, *args, **kw)
