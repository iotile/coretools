import proxy12
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.commander.cmdstream import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from time import sleep
from pymomo.utilities.typedargs.annotate import annotated,param,returns, context
from pymomo.utilities import typedargs

@context("UltrasonicModule")
class UltrasonicModule (proxy12.MIB12ProxyObject):
	"""
	Ultrasonic Flow and Level Measurement Module
	"""

	def __init__(self, stream, addr):
		super(UltrasonicModule, self).__init__(stream, addr)
		self.name = 'Ultrasonic Module'

	@param("power", "boolean", desc="true to enable power")
	def set_power(self, power):
		"""
		Enable power to ultrasonic chipset
		"""

		self.rpc(110, 0, int(power))