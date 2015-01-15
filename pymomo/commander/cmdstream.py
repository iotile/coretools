from exceptions import TimeoutException

class CMDStream:
	"""
	Send command frames over a transport layer and receive the response
	This converts a byte oriented stream to a frame oriented one.
	"""

	#Types of frame markers
	ACK = 0x06
	NACK = 0x15
	term_chars = [ACK, NACK]

	OkayResult = 0
	ErrorResult = 1

	def __init__(self, transport):
		self.trans = transport

	def parse_term(self, char):
		term = ord(char)

		if term == CMDStream.ACK:
			result = CMDStream.OkayResult
		elif term == CMDStream.NACK:
			result = CMDStream.ErrorResult
		else:
			raise ValueError("Invalid terminator character encountered: %d" % term)

		return result

	def read_frame(self):
		buffer, tchar = self.trans.read_until(CMDStream.term_chars)
		return buffer, self.parse_term(tchar)

	def send_cmd(self, cmd):
		"""
		Given a cmd string, append a newline if required and send it, waiting for
		the response.
		"""

		#Convert the command to a unicode object
		if not isinstance(cmd, basestring) and hasattr(cmd, "__str__"):
			cmdstr = cmd.__str__()
		else:
			cmdstr = cmd

		if cmdstr[-1] != '\n':
			cmdstr += '\n'

		self.trans.write(cmdstr)

		#If there is a custom result handler, use that, otherwise read a standard frame
		if hasattr(cmd, 'handle_result'):
			return cmd.handle_result(self)
		else:
			return self.read_frame()

	def heartbeat(self):
		"""
		Send a heartbeat character on the line that the FSU should respond to with
		the same character if it is working correctly.  Return true if the heartbeat
		was received, return false otherwise.
		"""


		self.trans.write(chr(255))
		
		c = self.trans.read()
		if len(c) == 0 or c[0] != chr(255):
			print "'%s'" % c
			return False 

		return True

	def reset(self):
		self.trans.write(chr(0))
		c = self.trans.read()
		if len(c) == 0 or c[0] != chr(1):
			print "'%s'" % c
			return False 

		return True