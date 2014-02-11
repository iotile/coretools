
from command import Command
from pymomo.cmdr.exceptions import *

class RPCCommand (Command):
	def __init__(self, address, feature, command, *args):
		"""
		Create an RPC command 
		"""

		self.addr = int(address)
		self.feat = int(feature)
		self.cmd = int(command)

		self.args = args
		self.result = ""

	def __str__(self):
		cmd = "rpc %d %d %d" % (self.addr, self.feat, self.cmd)
		argstr = " ".join(self._format_args())

		if len(argstr) > 0:
			cmd += " " + argstr

		return cmd

	def _format_args(self):
		fmtd = []

		for arg in self.args:
			if isinstance(arg, int) or isinstance(arg, long):
				fmtd.append(str(arg))
			else:
				fmtd.append(arg)

		return fmtd


	def handle_result(self, stream):
		"""
		rpc command on 
		"""
		status = ord(stream.trans.read())
		self.status = status

		if status == 254:
			buf, term = stream.read_frame()
			self.result = buf
			return buf, term

		if status == 0:
			num_bytes = ord(stream.trans.read())
			buf = stream.trans.read(num_bytes)
			self.result = buf

		seq = stream.trans.read()
		self.status = status

		return self.result, stream.parse_term(seq)

	def parse_result(self, num_ints, buff):
		parsed = {'ints':[], 'buffer':"", 'status': self.status, 'error': 'No Error'}

		if self.status == 254:
			parsed['error'] = self.result
			return parsed
		elif self.status != 0:
			parsed['error'] = 'MIB Error'
			return parsed

		#Otherwise, parse the results according to the type information given
		size = len(self.result)

		if size < 2*num_ints:
			raise RPCException('Return value too short to unpack', self.result)
		elif buff == False and size != 2*num_ints:
			raise RPCException('Return value does not match return type', self.result)

		for i in xrange(0, num_ints):
			low = ord(self.result[2*i])
			high = ord(self.result[2*i + 1])
			parsed['ints'].append((high << 8) | low)

		if buff:
			parsed['buffer'] = self.result[2*num_ints:]

		return parsed
