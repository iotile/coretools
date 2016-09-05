# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#MIB Proxy Objects

from iotilecore.commander.commands import RPCCommand
from iotilecore.commander.exceptions import *
from iotilecore.utilities.typedargs import return_type, annotated, param
from time import sleep
from iotilecore.utilities.packed import unpack

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

		unpack_flag = False
		if "result_type" in kw:
			res_type = kw['result_type']
		elif "result_format" in kw:
			unpack_flag = True
			res_type = (0, True)
		else:
			res_type = (0, False)

		try:
			res = self._parse_rpc_result(status, payload, *res_type)
			if unpack_flag:
				return unpack("<%s" % kw["result_format"], res['buffer'])

			return res
		except ModuleBusyError:
			pass

		if "retries" not in kw:
			kw['retries'] = 10

		#Sleep 100 ms and try again unless we've exhausted our retry attempts
		if kw["retries"] > 0:
			kw['retries'] -= 1

			sleep(0.1)
			return self.rpc(feature, cmd, *args, **kw)

	@return_type("basic_dict")
	def status(self):
		"""
		Query the status of an IOTile including its name and version
		"""

		hw_type, name, major, minor, patch, status = self.rpc(0x00, 0x04, result_format="H6sBBBB")

		status = {
			'hw_type': hw_type,
			'name': name,
			'version': (major, minor, patch),
			'status': status
		}

		return status

	@param("wait", "float", desc="Time to wait after reset for tile to boot up to a usable state")
	def reset(self, wait=1.0):
		"""
		Immediately reset this tile.
		"""
		try:
			self.rpc(0x00, 0x01)
		except ModuleNotFoundError:
			pass

		sleep(wait)

	@return_type("string")
	def tile_name(self):
		stat = self.status()

		return stat['name']

	@return_type("list(integer)", formatter="compact")
	def tile_version(self):
		stat = self.status()

		return stat['version']

	@return_type("map(string, bool)")
	def tile_status(self):
		"""	
		Get the current status of this tile

		Returns a 
		"""
		stat = self.status()

		flags = stat['status']

		#FIXME: This needs to stay in sync with lib_common: cdb_status.h
		status = {}
		status['debug_mode'] = bool(flags & (1 << 3))
		status['configured'] = bool(flags & (1 << 1))
		status['app_running'] = bool(flags & (1 << 0))
		status['trapped'] = bool(flags & (1 << 2))

		return status


	def _parse_rpc_result(self, status, payload, num_ints, buff):
		"""
		Parse the response of an RPC call into a dictionary with integer and buffer results
		"""

		parsed = {'ints':[], 'buffer':"", 'error': 'No Error', 'is_error': False}
		parsed['status'] = status
		parsed['return_value'] = status & 0b00111111

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
			low = (payload[2*i])
			high = (payload[2*i + 1])
			parsed['ints'].append((high << 8) | low)

		if buff:
			parsed['buffer'] = payload[2*num_ints:]

		return parsed
