#MIB Proxy Objects

from pymomo.commander.commands import RPCCommand
from pymomo.commander.exceptions import *
from time import sleep

class MIBProxyObject (object):
	def __init__(self, stream, address):
		self.stream = stream
		self.addr = address

	def rpc(self, feature, cmd, *args, **kw):
		"""
		Send an RPC call to this module, interpret the return value
		according to the result_type kw argument.  Unless raise keyword
		is passed with value False, raise an RPCException if the command
		is not successful.
		"""

		status, payload = self.stream.send_rpc(self.addr, feature, cmd, *args, **kw)

		if "result_type" in kw:
			res_type = kw['result_type']
		else:
			res_type = (0, False)

		try:
			return self._parse_rpc_result(status, payload, *res_type)
		except ModuleBusyError:
			pass

		if "retries" not in kw:
			kw['retries'] = 10

		#Sleep 100 ms and try again unless we've exhausted our retry attempts
		if kw["retries"] > 0:
			kw['retries'] -= 1

			sleep(0.1)
			return self.rpc(feature, cmd, *args, **kw)

	def _parse_rpc_result(self, status, payload, num_ints, buff):
		"""
		Parse the response of an RPC call into a dictionary with integer and buffer results
		"""

		parsed = {'ints':[], 'buffer':"", 'error': 'No Error', 'is_error': False}
		parsed['status'] = status

		#Check for protocol defined errors
		if not status & (1<<6):
			if status == 2:
				raise UnsupportedCommandError(address=self.addr)
			
			raise RPCError("Unknown status code received from RPC call", address=self.addr, status_code=status)


		#Otherwise, parse the results according to the type information given
		size = len(payload)

		if size < 2*num_ints:
			raise RPCError('Return value too short to unpack', expected_minimum_size=2*num_ints, actual_size=size, status_code=status, payload=payload)
		elif buff == False and size != 2*num_ints:
			raise RPCError('Return value was not the correct size', expected_size=2*num_ints, actual_size=size, status_code=status, payload=payload)

		for i in xrange(0, num_ints):
			low = ord(payload[2*i])
			high = ord(payload[2*i + 1])
			parsed['ints'].append((high << 8) | low)

		if buff:
			parsed['buffer'] = payload[2*num_ints:]

		return parsed

	def verbose_printer(self, verbose):
		def print_verb(str):
			if verbose:
				print str

		return print_verb
