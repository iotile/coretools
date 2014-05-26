#MIB Proxy Objects

from pymomo.commander.commands import RPCCommand
from pymomo.commander.exceptions import *

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


		r = RPCCommand(self.addr, feature, cmd, *args)
		self.stream.send_cmd(r)

		if "result_type" in kw:
			res_type = kw['result_type']
		else:
			res_type = (0, False)

		res = r.parse_result(*res_type)

		if "raise" not in kw or kw['raise'] == True:
			if res['status'] != 0:
				raise RPCException(res['status'], res['error'])

		return res

	def verbose_printer(self, verbose):
		def print_verb(str):
			if verbose:
				print str

		return print_verb