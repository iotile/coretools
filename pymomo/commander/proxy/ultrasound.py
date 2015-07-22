from pymomo.commander.proxy import proxy12
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from time import sleep
from pymomo.utilities.typedargs.annotate import annotated,param,return_type, context
from pymomo.utilities.typedargs import iprint
from pymomo.utilities import typedargs
from itertools import product
from pymomo.exceptions import *
import math

@context("UltrasonicModule")
class UltrasonicModule (proxy12.MIB12ProxyObject):
	"""
	Ultrasonic Flow and Level Measurement Module

	This module contains the analog and digital logic to perform
	ultrasonic flow and level measurements using the TDC1000 and
	TDC7200 chips from Texas Instruments.
	"""

	#A list of all (gain, threshold) combinations that the TDC1000 supports ordered from highest gain to lowest gain
	gain_settings = [(41, 0), (38, 0), (41, 1), (35, 0), (38, 1), (41, 2), (32, 0), (35, 1), (38, 2), (41, 3), (29, 0), (32, 1), (35, 2),
(38, 3), (26, 0), (29, 1), (32, 2), (41, 4), (35, 3), (23, 0), (26, 1), (29, 2), (38, 4), (21, 0), (32, 3), (20, 0), 
(23, 1), (41, 5), (26, 2), (35, 4), (18, 0), (29, 3), (21, 1), (20, 1), (38, 5), (23, 2), (32, 4), (15, 0), (26, 3), 
(18, 1), (21, 2), (41, 6), (35, 5), (20, 2), (29, 4), (12, 0), (23, 3), (15, 1), (18, 2), (38, 6), (32, 5), (26, 4), 
(21, 3), (9, 0), (20, 3), (12, 1), (15, 2), (41, 7), (35, 6), (29, 5), (23, 4), (18, 3), (6, 0), (9, 1), (12, 2), 
(38, 7), (32, 6), (21, 4), (26, 5), (20, 4), (15, 3), (3, 0), (6, 1), (9, 2), (35, 7), (29, 6), (18, 4), (23, 5), 
(12, 3), (0, 0), (3, 1), (21, 5), (6, 2), (32, 7), (26, 6), (15, 4), (20, 5), (9, 3), (0, 1), (18, 5), (3, 2), (29, 7), 
(23, 6), (12, 4), (6, 3), (21, 6), (15, 5), (0, 2), (26, 7), (20, 6), (9, 4), (3, 3), (18, 6), (12, 5), (23, 7), (6, 4), 
(0, 3), (21, 7), (15, 6), (9, 5), (20, 7), (3, 4), (18, 7), (12, 6), (6, 5), (0, 4), (15, 7), (9, 6), (3, 5), (12, 7), 
(6, 6), (0, 5), (9, 7), (3, 6), (6, 7), (0, 6), (3, 7), (0, 7)]

	def __init__(self, stream, addr):
		super(UltrasonicModule, self).__init__(stream, addr)
		self.name = 'Ultrasonic Module'

		self.gain = 18
		self.threshold = 1
		self.pulses = 8
		self.mask = 5

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
	@return_type("integer", formatter="hex")
	def read_tdc7200_24bit(self, address):
		"""
		Read a 24-bit register from the TDC7200 stopwatch chip
		"""

		res = self.rpc(110, 5, address, result_type=(0, True))
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

	def _generate_thresholds(self):
		"""
		Generate a map of all of the threshold voltages that the TDC1000 supports.
		"""

		thresh = [35., 50., 75., 125., 220., 410., 775., 1500.]
		thresh_code = [0, 1, 2, 3, 4, 5, 6, 7]
		gain1 = [0, 3, 6, 9, 12, 15, 18, 21]
		gain1_code = [0, 1, 2, 3, 4, 5, 6, 7]
		gain2 = [0, 20]
		gain2_code = [False, True]

		items = product(gain1, gain2, thresh)

		output = map(lambda x: x[2] * pow(10.0, -(x[0] + x[1])/20.0), items)
		codes = [x for x in product(gain1_code, gain2_code, thresh_code)]

		return {output[i]: codes[i] for i in xrange(0, len(codes))}

	def _generate_gains(self):
		"""
		Generate a map of all of the gains that the TDC1000 supports.
		"""

		gain1 = [0, 3, 6, 9, 12, 15, 18, 21]
		gain1_code = [0, 1, 2, 3, 4, 5, 6, 7]
		gain2 = [0, 20]
		gain2_code = [False, True]

		items = product(gain1, gain2)

		output = map(lambda x: x[0] + x[1], items)
		codes = [x for x in product(gain1_code, gain2_code)]

		return {output[i]: codes[i] for i in xrange(0, len(codes))}

	@return_type("map(string,bool)")
	def tdc1000_get_error(self):
		"""
		Get the error flags register from the tdc1000 module
		"""

		val = self.read_tdc1000(7)

		out = {}
		out['high_signal'] = bool(val & (1 << 0))
		out['no_signal'] = bool(val & (1 << 1))
		out['weak_signal'] = bool(val & (1 << 2))

		return out

	@return_type("map(string,bool)")
	def tdc7200_get_error(self):
		"""
		Get the error flags register from the tdc7200 module
		"""

		val = self.read_tdc7200(2)
		out = {}
		out['new_measurement'] = bool(val & (1 << 0))
		out['coarse_overflow'] = bool(val & (1 << 1))
		out['clock_overflow'] = bool(val & (1 << 2))
		out['measurement_started'] = bool(val & (1 << 3))
		out['measurement_complete'] = bool(val & (1 << 3))

		return out

	@param("gain", "integer", desc="Total gain to use")
	@param("pulses", "integer", "positive", desc="Number of pulses to transmit")
	@param("threshold", "integer", desc="Treshold to use for qualifying echos (0-7)")
	@param("mask", "float", desc="Number of microseconds to mask (rounded to nearest 8th of a microsecond")
	def set_parameters(self, gain, pulses, threshold, mask):
		"""
		Set measurement parameters for future measurements.
		"""

		self.gain = gain
		self.pulses = pulses
		self.threshold = threshold
		self.mask = mask

		mask_cycles = int(self.mask*8)
		self.rpc(110,7, self.gain, self.threshold, self.pulses, mask_cycles)

	@return_type("map(string, integer)")
	def get_parameters(self):
		"""
		Return a dictionary containing the current settings for the TOF measurements
		"""

		res = self.rpc(110, 0xC, result_type=(3, False))

		params = {}
		params['gain'] = res['ints'][0]
		params['threshold'] = res['ints'][1]
		params['pulses'] = res['ints'][2]

		return params

	@return_type('list(integer)')
	@param("direction", "integer", ("range", 0, 1), desc="Measurement direction (0 or 1)")
	def take_tof(self, direction):
		"""
		Take a single TOF measurement in one direction and return the first 5 echos
		"""

		res = self.rpc(110, 0xE, direction, result_type=(0, True))

		tof0,tof1,tof2,tof3,ints = struct.unpack_from("<llllB", res['buffer'])

		iprint("Interrupt Flags Register: %s" % bin(ints))
		return [tof0, tof1, tof2, tof3]

	@return_type("integer")
	def find_signal(self):
		"""
		Find the ultrasonic signal strength
		"""

		res = self.rpc(110, 0xF, result_type=(0,True))

		signal, = struct.unpack_from("<B", res['buffer'])
		return signal

	@annotated
	def find_optimal_gain(self):
		"""
		Find the optimal gain setting for minimizing variance in the measurement
		"""

		res = self.rpc(110, 0x10, result_type=(0, True), timeout=60.)

		variance, index, err = struct.unpack_from("<lbB", res['buffer'])

		if index < len(self.gain_settings):
			gain_setting = self.gain_settings[index]

			print "Standard Deviation: %d ps" % (math.sqrt(variance)*16.0,)
			print "Expected Deviation at 128 averages: %d ps" % (math.sqrt(variance)*16.0/math.sqrt(128.0),)
			print "Gain Setting: %d db gain, %d threshold" % gain_setting
		
		print "Error Code: %d" % err

	@return_type("integer")
	def last_automatic_reading(self):
		res = self.rpc(110, 0x11, result_type=(0, True), timeout=3.)

		reading, = struct.unpack_from("<l", res['buffer'])

		return reading*16

	@param("average_bits", "integer", desc="log2(number of averages to take)")
	@param("mode", "string", ("list", ['fast', 'robust']))
	@return_type('list(integer)')
	def tof_difference(self, average_bits, mode='robust'):
		"""
		Figure out the time of flight difference in two directions

		No filtering other than the built-in median filter is performed
		and the raw delta TOF is reported in picoseconds.
		"""

		if mode == 'robust':
			fast = 0
		else:
			fast = 1

		res = self.rpc(110, 8, average_bits, fast, result_type=(0, True))

		diff,num,err = struct.unpack_from("<lLB", res['buffer'])

		if err != 0:
			iprint("Error code returned from measurement: %d" % err)
		
		if fast:
			return [int(diff*16),]

		if num == 0:
			return []

		return [int(diff*16)]

	@param("direction", "integer", desc="Direction of TOF readings to get (1 or 2)")
	@return_type("list(integer)")
	def get_tofs(self, direction):
		res = self.rpc(110, 0xD, direction, result_type=(0, True))

		tofs = struct.unpack_from("<lllll", res['buffer'])
		return tofs

	@return_type("integer")
	@param("gain", "integer", "positive", desc="Gain to use")
	@param("threshold", "integer", "nonnegative", desc="Threshold id")
	def setting_variance(self, gain, threshold):
		"""
		Estimate the delta TOF variance in measurement accuracy
		"""

		res = self.rpc(110, 0xA, gain, threshold, result_type=(0, True))

		var, = struct.unpack_from("<l", res['buffer'])
		
		return var

	@return_type("list(float)")
	def get_pulse_deviations(self):
		"""
		Get the standard deviation of delta TOF for each pulse in the 5 pulse train
		"""

		from math import sqrt

		res = self.rpc(110, 9, result_type=(0, True), timeout=30.0)

		variances = struct.unpack_from('<lllll', res['buffer'])
		
		stds = [sqrt(x)*16.0 for x in variances]
		return stds

	@param("averages", "integer", "nonnegative", desc="Number of averages per sample (in log2)")	
	@param("count", "integer", "positive", desc="Number of samples to take")
	@return_type("list(float)")
	def tof_histogram(self, averages, count):
		"""
		Get a list of <<count>> TOF deltas for building a histogram
		"""

		vals = []

		for i in xrange(0, count):
			val = self.tof_difference(averages)
			vals.extend(val)

		return vals