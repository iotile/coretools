#proxy12.py
#Proxy object for all modules that have a mib12 executive

import proxy
from pymomo.utilities.typedargs.annotate import returns, param, annotated, return_type, context
from collections import namedtuple
from pymomo.commander.exceptions import *
import struct

#Printer functions for displaying return values.
def print_status(status):
	"""
	Break out executive status bits and print them.
	"""

	print "Executive Status Register"
	print "Serial Number: %d" % status.serial
	print "HW Type: %d" % status.hwtype
	print "First Application Row: %d" % status.approw
	print "Runtime Status: 0x%X" % status.status

	if status.trapped:
		print "\n***Module has crashed and is waiting for debugging; trap bit is set.***\n"
	else:
		print "\nModule is running normally.\n"

@context("MIB12ProxyObject")
class MIB12ProxyObject (proxy.MIBProxyObject):
	"""
	Proxy object for all 8-bit PIC modules that run the pic12_executive.
	Executive functionality is implemented here.
	"""

	#Know Configuration Variable Types
	config_types = {6: 'array', 7: 'string'}

	@returns(desc='application firmware checksum', data=True)
	def checksum(self):
		"""
		Get the 8-bit application checksum.
		"""
		return self.rpc(0,2, result_type=(1,False))['ints'][0]

	@returns(desc='module status register', data=True, printer=print_status)
	def status(self):
		"""
		Get the module status register.

		Returns executive version, runtime parameters, hw type, executive size and whether the module has crashed.
		"""

		res = self.rpc(0,4, result_type=(2,False))
		status = namedtuple("ExecutiveStatus", ['serial', 'hwtype', 'approw', 'status', 'trapped'])

		status.serial = res['ints'][0] & 0xFF
		status.hwtype = res['ints'][0] >> 8
		status.approw = res['ints'][1] & 0xFF
		status.status = res['ints'][1] >> 8
		status.trapped = bool(status.status & 1<<7) 

		return status

	@param('location','integer','nonnegative',desc='RAM address to read')
	@param('type', 'string', ('list', ['uint8']), desc='Type of variable to read (supports: uint8)')
	@returns(desc='variable contents', data=True)
	def readram(self, location, type='uint8'):
		res = self.rpc(0,3, location, result_type=(0,True))
		return ord(res['buffer'][0])

	@annotated
	def reset(self):
		"""
		Reset the application module.
		"""

		try:
			self.rpc(0, 1)
		except ModuleNotFoundError:
			pass

	@return_type("bool")
	def config_interface_supported(self):
		if hasattr(self, 'config_interface_support_status'):
			return self.config_interface_support_status

		try:
			res = self.rpc(255, 0, result_type=(1, False))
			self.config_interface_support_status = True
		except UnsupportedCommandError:
			self.config_interface_support_status = False

		return self.config_interface_support_status

	@return_type("integer")
	def count_config_variables(self):
		"""
		Count the number of configuration variables defined by the module
		"""

		if not self.config_interface_supported():
			raise HardwareError("Configuration interface is not supported by this module", address=self.addr)

		res = self.rpc(255, 0, result_type=(1,False))
		count = res['ints'][0]

		return count

	@return_type("map(string, integer)")
	@param("index", "integer", desc="Module specific index of variable to describe")
	def describe_config_variable(self, index):
		"""
		Describe the module's configuration variable named in the argument
		"""

		res = self.rpc(255, 1, result_type=(0, True))

		name, address, buffer_size, current_size, type = struct.unpack("<HHHHB", res['buffer'])

		return {'name': name, 'address': address, 'buffer_size': buffer_size, 'current_size': current_size, "type": type}

	@param("name", "integer", desc="Variable id to query")
	def clear_config_variable(self, name):
		"""
		Erase the contents of this configuration variable
		"""

		res = self.rpc(255, 4, name, result_type=(0, True))
		if ord(res['buffer'][0]) != 0:
			raise RPCError("Could not clear configuration variable", name=name, error_code=ord(res['buffer'][0]))

	def _config_type_name(self, type):
		if type not in self.config_types:
			return 'unknown type'

		return self.config_types[type]

	def _build_config_list(self):
		if hasattr(self, '_config_variable_list'):
			return

		num_vars = self.count_config_variables()

		self._config_variable_list = {}

		for i in xrange(0, num_vars):
			var = self.describe_config_variable(i)
			var['index'] = i
			del var['current_size']

			self._config_variable_list[var['name']] = var

	@return_type("map(string, string)")
	def list_config_variables(self):
		"""
		Return a map of the defined configuration variables and their types
		"""

		num_vars = self.count_config_variables()

		out_vars = {}

		for i in xrange(0, num_vars):
			var = self.describe_config_variable(i)
			sig = self._config_type_name(var['type'])
			if var['type'] > 5:
				sig += '[%d]' % var['buffer_size']

			out_vars[str(var['name'])] = sig

		return out_vars

	@param("value", "string", desc="parameter value to write")
	@param("name", "string", desc="parameter name to write")
	def set_config_variable(self, name, value):
		"""
		Write a value to a configuration variable

		Paremeters name and value should both be string types.  If name is convertible to an integer,
		it will be converted and its value will be used as the 16-bit name of the config variable.  If it is not
		convertible, it will be assumed to be a symbolic name and (in the future) looked up in the table of known
		config variable names.  Currently this is unsupported.
		"""

		self._build_config_list()

		try:
			int_name = int(name, 0)
		except ValueError:
			raise ArgumentError("Could not convert configuration variable name to an integer", name=name)

		try:
			var_info = self._config_variable_list[int_name]
		except KeyError:
			raise ArgumentError("Unknown config variable name not defined in module", name=int_name, known_names=self._config_variable_list.keys())

		self.clear_config_variable(int_name)
		typestr = self._config_type_name(var_info['type'])

		if typestr == 'string' or typestr == 'array':
			for i in xrange(0, len(value), 16):
				chuck_size = min(16, len(value) - i)

				res = self.rpc(255, 3, int_name, i, value[i:i+chuck_size], result_type=(0, True))
				result = ord(res['buffer'][0])
				written_length = ord(res['buffer'][1])

				if result != 0:
					raise RPCError("Could not set configuration value, module returned an error code", error=result, offset=i, chuck_size=chuck_size, variable_info=var_info)
		else:
			raise InternalError("Other configuration variable types are not currently supported")

	@param("name", "string", desc="parameter name to read")
	@return_type("string")
	def get_config_variable(self, name):
		"""
		Read the value of a configuration variable
		"""

		self._build_config_list()

		try:
			int_name = int(name, 0)
		except ValueError:
			raise ArgumentError("Could not convert configuration variable name to an integer", name=name)

		try:
			var_info = self._config_variable_list[int_name]
		except KeyError:
			raise ArgumentError("Unknown config variable name not defined in module", name=int_name, known_names=self._config_variable_list.keys())

		#Query to get the variable size
		res = self.rpc(255, 2, int_name, 0, 18, result_type=(0, True))
		result = ord(res['buffer'][0])
		length = ord(res['buffer'][1])

		data = ""
		for i in xrange(0, length, 18):
			chuck_size = min(18, length - i)
			res = self.rpc(255, 2, int_name, i, chuck_size, result_type=(0, True))
			result = ord(res['buffer'][0])
			if result != 0:
				raise RPCError("Could not get configuration value, module returned an error code", error=result, offset=i, chuck_size=chuck_size, variable_info=var_info)

			data += res['buffer'][2:]

		return data