import proxy12
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from time import sleep

class MultiSensorModule (proxy12.MIB12ProxyObject):
	ranges = {'offset': set(range(0, 256)), 'gain1': set(range(0, 128)), 'gain2':set(range(0,8)), 'delay': set(range(1, 256)), 
				'invert': set(['yes', 'no']), 'select':set(['current', 'differential'])}
	mapper = {'yes': 1, 'no': 0, 'current': 1, 'differential': 0}
	ids = {'offset': 0, 'gain1': 1, 'gain2': 2, 'select': 3, 'invert': 4, 'delay': 5}
	integral = set(['offset', 'gain1', 'gain2', 'delay'])

	def __init__(self, stream, addr):
		super(MultiSensorModule, self).__init__(stream, addr)
		self.name = 'MultiSensor Module'

	def set_parameter(self, name, value):
		if name not in self.ranges:
			raise KeyError("Invalid parameter options are: %s" % str(self.ranges.keys()))

		if name in self.integral:
			value = int(value)

		valid = self.ranges[name]
		if value not in valid:
			raise ValueError("Invalid parameter value for key %s" % name)

		if not isinstance(value, int):
			if value not in self.mapper:
				raise ValueError("Invalid parameter value for key %s, cannot be mapped to a known integer" % name)

			value = self.mapper[value]

		self.rpc(20, 3, self.ids[name], value)

	def set_sensor_push(self, push):
		"""
		Set whether the sensor module should push sensor data to the controller.
		"""

		res = self.rpc(20, 11, int(push))

	def read_voltage(self):
		res = self.rpc(20, 5, result_type=(1,False))
		return res['ints'][0]

	def acquire_pulses(self):
		"""
		Tell the multisensor module to sample flow rate for 1 sampling period.
		"""

		self.rpc(20, 6)

	def read_pulses(self):
		"""
		Return a list of all of the pulse widths and intervals between pulses
		acquired during the last acquisition period.

		Returns a 2-tuple containing the list of valid pulses and the
		number of invalid pulses
		"""

		res = self.rpc(20, 7, result_type=(2, False))
		counts = res['ints'][0]
		invalid = res['ints'][1]

		pulses = []
		for i in xrange(0, counts):
			res = self.rpc(20, 8, i, result_type=(2, False))
			width = res['ints'][0]
			interval = res['ints'][1]

			if i == counts-1:
				interval = 0

			pulses.append((width, interval))

		return pulses, invalid

	def read_median(self):
		"""
		Find the median of the list of pulse intervals recorded
		and return it.  This call is not idempotent since finding
		the median required destroying the list of recorded intervals
		"""
		res = self.rpc(20, 10, result_type=(1,False))

		return res['ints'][0]

	def read_periods(self):
		"""
		Return the number of periods that have been sampled.
		"""

		res = self.rpc(20, 9, result_type=(1, False))

		return res['ints'][0]
