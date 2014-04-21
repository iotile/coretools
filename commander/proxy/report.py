import proxy
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.commander.cmdstream import *
from pymomo.utilities.console import ProgressBar
import struct
from intelhex import IntelHex
from time import sleep

class ReportModule (proxy.MIBProxyObject):
	def __init__(self, stream, addr):
		super(ReportModule, self).__init__(stream, addr)
		self.name = 'GSM Module'

	def start(self):
		"""
		Start regular reporting
		"""
		self.rpc(60, 1)

	def stop(self):
		"""
		Stop regular reporting
		"""
		self.rpc(60, 2)

	def send(self):
		"""
		Send a single report
		"""

		self.rpc(60, 0)