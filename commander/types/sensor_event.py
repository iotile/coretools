from pymomo.commander.exceptions import *
from datetime import datetime
import struct

class SensorEvent:
	"""
	An event logged by a sensor module
	"""

	def __init__(self, buffer):
		if len(buffer) != 12:
			raise TypeException( 'SensorEvent', 'Length should have been 12, was %d' % len(buffer) )

		stream, metadata, timestamp_year, timestamp_month, timestamp_day, timestamp_hours, timestamp_minutes, timestamp_seconds, value = struct.unpack('BBBBBBBBI', buffer)

		if timestamp_year < 1960:
			timestamp_year = 1960
		timestamp_month += 1 # no 0th month in python
		timestamp_day += 1

		self.stream = stream
		self.metadata = metadata
		self.timestamp = datetime(timestamp_year, timestamp_month, timestamp_day, timestamp_hours, timestamp_minutes, timestamp_seconds)
		self.value = value