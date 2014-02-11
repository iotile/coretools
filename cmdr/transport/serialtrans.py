import serial
import transport
import io

class SerialTransport (transport.Transport):
	"""
	Standard serial port transport layer
	"""

	def __init__(self, dev, baud=115200, timeout=1):
		self.io = serial.Serial(port=dev, baudrate=baud, timeout=timeout)

	def write(self, buffer):
		for b in buffer:
			self.io.write(b)
		
		self.io.flush()

	def read(self, cnt=1):
		return self.io.read(cnt)

	def close(self):
		self.port.close