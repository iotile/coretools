import proxy12
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.commander.cmdstream import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from time import sleep
from pymomo.utilities.typedargs.annotate import annotated,param,return_type, context
from pymomo.utilities import typedargs

@context("UltrasonicModule")
class UltrasonicModule (proxy12.MIB12ProxyObject):
	"""
	Ultrasonic Flow and Level Measurement Module

	This module contains the analog and digital logic to perform
	ultrasonic flow and level measurements using the TDC1000 and
	TDC7200 chips from Texas Instruments.
	"""

	def __init__(self, stream, addr):
		super(UltrasonicModule, self).__init__(stream, addr)
		self.name = 'Ultrasonic Module'

	@param("power", "bool", desc="true to enable power")
	def set_power(self, power):
		"""
		Enable power to ultrasonic chipset
		"""

		self.rpc(110, 0, int(power))

	@param("address", "integer", desc="Address of register to read")
	@return_type("integer", formatter="hex")
	def read_tdc7200(self, address):
		"""
		Read an 8-bit register from the TDC7200 stopwatch chip
		"""

		res = self.rpc(110, 1, address, result_type=(0, True))

		return ord(res['buffer'][0])

	@param("address", "integer", desc="Address of register to read")
	@param("value", "integer", desc="Value to write")
	def write_tdc7200(self, address, value):
		"""
		Write an 8-bit register to the TDC7200 stopwatch chip
		"""

		res = self.rpc(110, 3, address, value)

	@param("address", "integer", desc="Address of register to read")
	def read_tdc7200_24bit(self, address):
		"""
		Read a 24-bit register from the TDC7200 stopwatch chip
		"""

		res = self.rpc(110, 5, address, value)
		lsb = ord(res['buffer'][0])
		nsb = ord(res['buffer'][1])
		msb = ord(res['buffer'][2])

		return (msb << 16) | (nsb << 8) | lsb


	@param("address", "integer", desc="Address of register to read")
	@return_type("integer", formatter="hex")
	def read_tdc1000(self, address):
		"""
		Read an 8-bit register from the TDC1000 ultrasonic frontend chip
		"""

		res = self.rpc(110, 2, address, result_type=(0, True))

		return ord(res['buffer'][0])

	@param("address", "integer", desc="Address of register to read")
	@param("value", "integer", desc="Value to write")
	def write_tdc1000(self, address, value):
		"""
		Write an 8-bit register to the TDC1000 ultrasonic frontend chip
		"""

		res = self.rpc(110, 4, address, value)

	@param("cycles", "integer", "positive", desc="Number of clock cycles to use (2, 10, 20 or 40)")
	@return_type("map(string,integer)")
	def oscillator_period(self, cycles):
		"""
		Determine the ring oscillator period of the TDC7200

		There is an extern 8 Mhz clock signal that the TDC7200 can use to calibrate
		itself and turn its ring oscillator periods into absolute time durations.  
		This routine uses the internal calibration feature of the TDC7200 to report 
		the ring oscillator period based on counting either 2, 10, 20 or 40 external
		clock periods.

		This routine automatically powers the TDC7200 on and off.
		"""

		if cycles not in [2, 10, 20, 40]:
			raise ArgumentError("cycles must be one of 2, 10, 20 or 40", cycles=cycles)

		config2 = (cycles << 6)
		config1 = (1 << 7) | (1 << 1) | 1
		
		self.set_power(True)
		
		self.write_tdc7200(1, config2)
		self.write_tdc7200(0, config1)

		sleep(0.1)

		cycle1 = self.read_tdc7200_24bit(0x1B)
		cycleN = self.read_tdc7200_24bit(0x1C)

		self.set_power(False)

		return {'1 cycle': cycle1, 'N cycles': cycleN}
