#proxy12.py
#Proxy object for all modules that have a mib12 executive

import proxy
from pymomo.utilities.typedargs.annotate import returns, param, annotated

class MIB12ProxyObject (proxy.MIBProxyObject):
	@returns(desc='application firmware checksum', data=True)
	def checksum(self):
		return self.rpc(1,2, result_type=(1,False))['ints'][0]