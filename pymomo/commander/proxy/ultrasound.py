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
from itertools import product
from pymomo.exceptions import *

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

	@param("time", "integer", desc="Masking period duration in 8ths of a microsecond")
	def set_masking_period(self, time):
		self.write_tdc7200(0x09, time & 0xFF)
		self.write_tdc7200(0x08, (time >> 8) & 0xFF)

	@param("cycles", "integer", "positive", desc="Number of clock cycles to use (2, 10, 20 or 40)")
	@return_type("map(string,integer)")
	def oscillator_period(self, cycles, do_power=True):
		"""
		Determine the ring oscillator period of the TDC7200

		There is an extern 8 Mhz clock signal that the TDC7200 can use to calibrate
		itself and turn its ring oscillator periods into absolute time durations.  
		This routine uses the internal calibration feature of the TDC7200 to report 
		the ring oscillator period based on counting either 2, 10, 20 or 40 external
		clock periods.

		This routine automatically powers the TDC7200 on and off.
		"""

		bit_map = {2: 0x00, 10: 0x01, 20: 0b10, 40: 0b11}
		if cycles not in bit_map:
			raise ArgumentError("cycles must be one of 2, 10, 20 or 40", cycles=cycles)

		config2 = (bit_map[cycles] << 6)
		config1 = (1 << 7) | (1 << 1) | 1
		
		if do_power:
			self.set_power(True)
		
		self.write_tdc7200(1, config2)
		self.write_tdc7200(0, config1)

		sleep(0.1)

		cycle1 = self.read_tdc7200_24bit(0x1B)
		cycleN = self.read_tdc7200_24bit(0x1C)

		if do_power:
			self.set_power(False)

		return {'1 cycle': cycle1, 'N cycles': cycleN}

	@param("cycles", "integer", "positive", desc="Number of clock cycles to use (2, 10, 20 or 40)")
	@param("averages", "integer", "positive", desc="Number of times to perform the measurement")
	def oscillator_jitter(self, cycles=10, averages=100):
		"""
		Measure the ring oscillator jitter

		Sample the ring oscillator period many times and compute the mean and std deviation
		given that the external oscillator frequency is 8 Mhz.
		"""

		times = []
		offsets = []
		self.set_power(True)

		for i in xrange(0, averages):
			res = self.oscillator_period(cycles, do_power=False)

			time1 = res['1 cycle']
			timeN = res['N cycles']

			count_est = (timeN - time1) / (cycles - 1.0)
			time_est = (1.0/8.0)/count_est * 1e6
			times.append(time_est)

			offset = abs(1.0/8.0*1e6 - time_est*time1)
			offsets.append(offset)
			
		self.set_power(False)

		print times
		print offsets

	@param("pulses", "integer", "positive", desc="Number of pulses to send")
	@param("gain", "integer", "positive", desc="Gain to use")
	@param("threshold", "integer", "nonnegative", desc="Threshold id")
	@return_type("list(float)")
	def find_echos(self, pulses, gain, threshold):
		"""
		Find all echos that we can at the desired sensitivity.

		Returns a list of the time of each echo that we can find.
		"""

		gains = self._generate_gains()
		if gain not in gains:
			raise ArgumentError("Unknown gain not in the list of supported gains", gain=gain, supported_gains=gains)

		gset = gains[gain]

		echos = []
		self.set_power(True)



		start_mask = 0.0

		while True:
			curr_echos = self.take_level_measurement(gset[0], gset[1], pulses, threshold, start_mask)
			if len(curr_echos) == 0:
				break

			start_mask = curr_echos[-1] + 1.0/8.
			echos += curr_echos

		self.set_power(False)

		return echos

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
	@param("pulses", "integer", "positive", desc="Number of pulses to send")
	@param("time", "float", "nonnegative", desc="Time of the echo to map")
	@return_type("float")
	def echo_amplitude(self, pulses, time):
		"""
		Determine the amplitude of the echo at the given time
		"""

		cycle_time = int(time*8.0)
		start_cycle = cycle_time - 2
		start_mask = start_cycle/8.0

		gains = self._generate_thresholds()

		gain_keys = sorted(gains.keys())
		gain_range = [0, len(gain_keys)-1]

		echos = self.take_level_measurement(7, True, pulses, 0, start_mask)

		if len(echos) == 0 or abs(echos[0] - time) > 0.5:
			raise InternalError("Could not find echo at requested time", time=time, start_mask=start_mask, found_echos=echos)

		echos = self.take_level_measurement(0, False, pulses, 7, start_mask)
		if len(echos) > 0 and abs(echos[0] - time) <= 0.5:
			return 1500.

		#Binary search to find the first gain where this echo does not occur
		while gain_range[0] < gain_range[1]:
			guess = (gain_range[0] + gain_range[1]) // 2
			guess_gain = gain_keys[guess]
			guess_settings = gains[guess_gain]

			echos = self.take_level_measurement(guess_settings[0], guess_settings[1], pulses, guess_settings[2], start_mask)

			#Check if echo disappeared
			if len(echos) == 0 or abs(echos[0] - time) > 0.5:
				gain_range[1] = guess - 1
			else:
				gain_range[0] = guess + 1

		guess_gain = gain_keys[gain_range[0]]
		return guess_gain

	@param('mode', 'string', desc='Type of measurement (level or flow)')
	@param("pulses", "integer", "positive", desc="Number of pulses to transmit")
	@return_type("map(float, float)")
	def map_echos(self, pulses):
		"""
		Find the amplitude of all received echos 

		Uses the programmable receive path of the TDC1000 to vary the threshold
		and gain of the receiving transducer in order to determine the best guess
		amplitude and time of each echo received in level measurement mode.

		Returns a map of TOF to amplitude in volts.
		"""

		echos = self.find_echos(pulses)

		self.set_power(True)

		ampl = {}
		for echo in echos:
			try:
				ampl[echo] = self.echo_amplitude(pulses, echo)

				print "%.2f: %.1f" % (echo, ampl[echo])
			except InternalError:
				print "%.2f: Error" % echo
				pass

		self.set_power(False)

		return ampl

	@param("gain", "integer", desc="Total gain to use")
	@param("pulses", "integer", "positive", desc="Number of pulses to transmit")
	@param("threshold", "integer", desc="Treshold to use for qualifying echos (0-7)")
	@param("mask", "float", desc="Number of microseconds to mask (rounded to nearest 8th of a microsecond")
	@param("cycles", "integer", desc="Number of cycles to average")
	@return_type("float")
	def average_level(self, gain, pulses, threshold, mask, cycles=10):
		"""
		Average N level measurements and return the mean
		"""

		total = 0.0
		cnt = 0

		self.set_power(True)

		for i in xrange(0, cycles):
			res = self.take_level_measurement(gain, pulses, threshold, mask)
			if len(res) > 0:
				total += res[0]
				cnt += 1

		self.set_power(False)
		return total/cnt

	@return_type("list(float)")
	def take_level_measurement(self):
		"""
		Instruct the ultrasonic module to take a level measurement

		The supplied parameters determine the analog gain and threshold limits as well
		as the number of pulses to transmit and how many must be received for a valid
		measurement.

		Returns a list of the times of each echo in microseconds.
		"""

		gains = self._generate_gains()
		if self.gain not in gains:
			raise ArgumentError("Unknown gain not in the list of supported gains", gain=gain, supported_gains=gains)

		gset = gains[self.gain]

		mask_cycles = int(self.mask*8)

		res = self.rpc(110, 6, pulses, 0, gset[0], int(not gset[1]), self.threshold, mask_cycles, 0b00, 1, result_type=(0, True))

		if len(res['buffer']) == 1:
			return []

		echos = []

		for i in xrange(0, 5):
			lsb = ord(res['buffer'][i*4 + 0])
			n1sb = ord(res['buffer'][i*4 + 1])
			n2sb = ord(res['buffer'][i*4 + 2])
			msb = ord(res['buffer'][i*4 + 3])

			tof = msb << 24 | n2sb << 16 | n1sb << 8 | lsb;
			if tof > 0:
				echos.append(float(tof)/1e6)

		return sorted(echos)

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

	@param("average", "integer", "positive", desc="Total gain to use")
	@return_type("float")
	def tof_difference(self, average):
		"""
		Figure out the time of flight difference in two directions
		"""

		res = self.rpc(110, 8, , result_type=(0, True))
		delta = struct.unpack_from("<l", res['buffer'])
		
		return float(delta)

	@param("average", "integer", "positive", desc="Number of averaging periods")
	@param("count", "integer", "positive", desc="Number of samples to get")
	@return_type("list(float)")
	def tof_histogram(self, average, count):
		vals = []

		for i in xrange(0, count):
			val = self.tof_difference(average)
			vals.append(val)

		return vals

	@return_type("list(float)")
	def take_tof_measurement(self, direction=0):
		"""
		Instruct the ultrasonic module to take a TOF measurement

		The supplied parameters determine the analog gain and threshold limits as well
		as the number of pulses to transmit and how many must be received for a valid
		measurement.

		Returns a list of the times of each tof pulse reception in microseconds.
		"""

		gains = self._generate_gains()
		if self.gain not in gains:
			raise ArgumentError("Unknown gain not in the list of supported gains", gain=gain, supported_gains=gains)

		gset = gains[self.gain]

		mask_cycles = int(self.mask*8)

		res = self.rpc(110, 6, self.pulses, 0, gset[0], int(not gset[1]), self.threshold, mask_cycles, 0b01, direction, result_type=(0, True))

		if len(res['buffer']) == 1:
			print "No echos"
			return []

		echos = []

		for i in xrange(0, 5):
			lsb = ord(res['buffer'][i*4 + 0])
			n1sb = ord(res['buffer'][i*4 + 1])
			n2sb = ord(res['buffer'][i*4 + 2])
			msb = ord(res['buffer'][i*4 + 3])

			tof = msb << 24 | n2sb << 16 | n1sb << 8 | lsb;
			if tof > 0:
				echos.append(float(tof)/1e6)

		return sorted(echos)