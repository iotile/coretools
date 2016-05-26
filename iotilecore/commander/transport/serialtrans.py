# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import serial
import transport
import io

class SerialTransport (transport.Transport):
	"""
	Standard serial port transport layer
	"""

	def __init__(self, dev, baud=125000, timeout=120):
		self.io = serial.Serial(port=dev, baudrate=baud, timeout=timeout)

	def write(self, buffer):
		for b in buffer:
			self.io.write(b)
		
		self.io.flush()

	def read(self, cnt=1):
		buf = self.io.read(cnt)
		return buf

	def close(self):
		self.port.close

	def receive_count(self):
		return self.io.inWaiting()
