import proxy
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.commander.cmdstream import *
from pymomo.utilities.console import ProgressBar
import struct
from intelhex import IntelHex
from time import sleep

class GSMModule (proxy.MIBProxyObject):
	def __init__(self, stream, addr):
		super(GSMModule, self).__init__(stream, addr)
		self.name = 'GSM Module'

	def power_module(self):
		"""
		Turn on power to the GSM module
		"""

		self.rpc(10, 1)

	def module_on(self):
		res = self.rpc(10, 0, result_type=(1, False))

		if res['ints'][0] == 1:
			return True

		print res['ints'][0]

		return False

	def at_cmd(self, cmd, wait=0.5):
		"""
		Send an AT command to the GSM module and wait for its
		response.
		"""

		res = self.rpc(10, 2, cmd, result_type=(0, True))

		return res['buffer']