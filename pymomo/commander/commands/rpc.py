from command import Command
from pymomo.commander.exceptions import *
import base64

class RPCCommand (Command):
	def __init__(self, address, feature, command, *args):
		"""
		Create an RPC command 
		"""

		self.addr = int(address)
		self.feat = int(feature)
		self.cmd = int(command)
		self.spec = 0

		self.args = args
		self.result = ""

	def __str__(self):
		args = self._format_args()
		header = bytearray(4)
		header[0] = self.addr
		header[1] = self.feat
		header[2] = self.cmd
		header[3] = self.spec

		packet = header + args

		cmd = "binrpc %s" % base64.standard_b64encode(packet)
		return cmd

	def _convert_int(self, arg):
		out = bytearray(2)

		out[0] = arg & 0xFF
		out[1] = (arg & 0xFF00) >> 8;

		converted = out[0] | (out[1] << 8)

		if converted != arg:
			raise ValueError("Integer argument was too large to fit in an rpc 16 bit int: %d" % arg)

		return out

	def _pack_arg(self, arg):
		if isinstance(arg, int) or isinstance(arg, long):
			return self._convert_int(arg), False
		elif isinstance(arg, bytearray):
			return arg, True
		elif isinstance(arg, basestring):
			return bytearray(arg), True

		raise ValueError("Unknown argument type could not be converted for rpc call.")

	def _format_args(self):
		fmtd = bytearray()

		num_ints = 0
		num_bufs = 0

		for arg in self.args:
			a,is_buf = self._pack_arg(arg)
			fmtd += a

			if is_buf:
				num_bufs += 1
				buff_len = len(a)

			if not is_buf:
				if num_bufs != 0:
					raise ValueError("Invalid rpc parameters, integer came after buffer.")

				num_ints += 1

		if num_bufs > 1:
			raise ValueError("You must pass at most 1 buffer. num_bufs=%d" % num_bufs)

		if num_ints > 4:
			raise ValueError("You must pass at most 4 integers. num_ints=%d" % num_ints)

		if len(fmtd) > 20:
			raise ValueError("Arguments are greater then the maximum mib packet size, size was %d" % len(fmtd))

		#Calculate the command type spec
		self.spec = len(fmtd)

		if len(fmtd) < 20:
			fmtd += bytearray(20 - len(fmtd))

		return fmtd


	def handle_result(self, stream):
		"""
		rpc command on 
		"""
		status_value = ord(stream.trans.read())
		status = status_value & 0b00111111

		self.status = status
		self.complete_status = status_value

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
			if self.status == 1:
				parsed['error'] = 'Unsupported Command'
			elif self.status == 2:
				parsed['error'] = 'Wrong Parameter Type'
			elif self.status == 3:
				parsed['error'] = 'Parameter Too Long'
			elif self.status == 4:
				parsed['error'] = 'Checksum Error'
			elif self.status == 6:
				parsed['error'] = 'Unknown Error'
			elif self.status == 7:
				parsed['error'] = 'Callback Error'
			elif self.complete_status == 0xFF:
				parsed['error'] = 'Module at address ' + str(self.addr) + ' not found.'
			else:
				parsed['error'] = 'Unrecognized MIB status code'
			return parsed

		#Otherwise, parse the results according to the type information given
		size = len(self.result)

		if size < 2*num_ints:
			raise RPCException(300, 'Return value too short to unpack : %s' % self.result)
		elif buff == False and size != 2*num_ints:
			raise RPCException(301, 'Return value does not match return type: %s' % self.result)

		for i in xrange(0, num_ints):
			low = ord(self.result[2*i])
			high = ord(self.result[2*i + 1])
			parsed['ints'].append((high << 8) | low)

		if buff:
			parsed['buffer'] = self.result[2*num_ints:]

		return parsed
