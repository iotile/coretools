import proxy
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.commander.cmdstream import *
from pymomo.utilities.console import ProgressBar
import struct
from intelhex import IntelHex
from time import sleep

class MultiSensorModule (proxy.MIBProxyObject):
	def __init__(self, stream, addr):
		super(MultiSensorModule, self).__init__(stream, addr)
		self.name = 'MultiSensor Module'

	def set_offset(self, offset):
		if offset < 0 or offset > 255:
			raise ValueError("Offset must be in the range [0, 255]")

		self.rpc(20, 5, offset)

	def set_stage1_gain(self, gain):
		if gain < 0 or gain > 127:
			raise ValueError("Stage 1 gain must be in the range [0, 127]")

		self.rpc(20, 3, gain)

	def set_stage2_gain(self, gain):
		if gain < 0 or gain > 7:
			raise ValueError("Stage 2 gain must be in the range [0, 7]")

		self.rpc(20, 4, gain)

	def read_voltage(self):
		res = self.rpc(20, 6, result_type=(1,False))
		return res['ints'][0] 

	def set_inverted(self, inverted):
		self.rpc(20, 7, int(bool(inverted)))
