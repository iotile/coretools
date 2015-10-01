from pymomo.commander.exceptions import *
import struct
import math

class PerformanceCounter:
	def __init__(self, buffer, type="timer", name="Unnamed"):
		if len(buffer) != 20:
			raise TypeException("PerformanceCounter initialized from buffer of length (%d), should be 20." % len(buffer))

		count, mean, minval, maxval, accum = struct.unpack("<LLLLL", buffer)

		self.count = count
		self.mean = mean
		self.accum = accum
		self.min = minval
		self.max = maxval
		self.name = name
		self.type = type

	def format_value(self, val):
		if self.type == "timer":
			us = val*0.25
			if us < 1e3:
				time = "%.2f us" % us
			elif us < 1e6:
				time = "%.2f ms" % (us/1000.0,)
			else:
				time = "%.2f s" % (us/1e6,)

			return "%s (%d cycles)" % (time, val)

		return str(val)

	def display(self):
		print "Performance Counter (%s)" % str(self.name)
		print "Number of Events: %d" % self.count
		print "Min: %s" % self.format_value(self.min)
		print "Max: %s" % self.format_value(self.max)
		print "Mean: %s" % self.format_value(self.mean)
