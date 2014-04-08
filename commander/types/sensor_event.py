from pymomo.commander.exceptions import *
from datetime import datetime
import struct

class SensorEvent:
	"""
	An event logged by a sensor module
	"""

	def __init__(self, buffer):
		if len(buffer) != 16:
			raise TypeException( 'SensorEvent', 'Length should have been 16, was %d' % len(buffer) )

		stream, metadata, timestamp_year, timestamp_month, timestamp_day, timestamp_hours, timestamp_minutes, timestamp_seconds, value = struct.unpack('BBBBBBBBQ', buffer)

		self.stream = stream
		self.metadata = metadata
		self.timestamp = datetime(timestamp_year, timestamp_month, timestamp_day, timestamp_hours, timestamp_minutes, timestamp_seconds)
		self.value = value