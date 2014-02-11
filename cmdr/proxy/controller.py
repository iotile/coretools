import proxy
from pymomo.cmdr.exceptions import *
from pymomo.cmdr.types import *

class MIBController (proxy.MIBProxyObject):
	def __init__(self, stream):
		super(MIBController, self).__init__(stream, 8)
		self.name = 'Controller'

	def count_modules(self):
		"""
		Count the number of attached devices to this controller
		"""

		res = self.rpc(42, 1, result_type=(1, False))
		return res['ints'][0]

	def describe_module(self, index):
		"""
		Describe the module given its module index
		"""
		res = self.rpc(42, 2, index, result_type=(0,True))

		return ModuleDescriptor(res['buffer'])

	def enumerate_modules(self):
		"""
		Get list of all attached modules and describe them all
		"""
		
		num = self.count_modules()

		mods = []

		for i in xrange(0, num):
			mods.append(self.describe_module(i))

		return mods
