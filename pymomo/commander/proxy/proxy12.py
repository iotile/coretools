#proxy12.py
#Proxy object for all modules that have a mib12 executive

import proxy
from pymomo.utilities.typedargs.annotate import returns, param, annotated, return_type, context
from collections import namedtuple
from pymomo.commander.exceptions import *
import struct
from pymomo.utilities import typedargs

MIBCommandMapIndex = 0
MIBInterfaceMapIndex = 1
MIBConfigurationMetadataIndex = 2
MIBConfigurationAddressIndex = 3

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

	@return_type("fw_mib12_status")
	def status(self):
		"""
		Get the module status register.

		Returns executive version, runtime parameters, hw type, executive size and whether the module has crashed.
		"""

		res = self.rpc(0,4, result_type=(0, True))
		
		return res['buffer']

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

	def _read_appinfo_table(self, table, offset):
		"""
		Read a single entry from the application info table specified by table
		"""

		res = self.rpc(0, 2, int(table), int(offset), result_type=(0, True))

		if len(res['buffer']) != 4:
			raise HardwareError("Invalid response with incorrect length from module reading appinfo table", actual_length=len(res['buffer']), desired_length=4, table=table, offset=offset)

		return res['buffer']

	@return_type("list(integer)")
	def list_interfaces(self):
		"""
		List all of the interfaces that this module supports

		Returns a list of all of the interfaces ids supporte by this module as
		4 byte
		"""

		interfaces = []
		#We don't support more than 100 interfaces so make sure we can't loop forever
		#if the application is corrupted somehow
		for i in xrange(0, 100):
			iface = self._read_appinfo_table(MIBInterfaceMapIndex, i)

			if ord(iface[0]) == 0xFF and ord(iface[1]) == 0xFF and ord(iface[2]) == 0xFF and ord(iface[3]) == 0xFF:
				break

			iface_num, = struct.unpack('<L', iface)
			interfaces.append(iface_num)

		return interfaces

	@annotated
	def config_manager(self):
		"""
		Get a configuration manager object to inspect and edit the configuration of this module
		"""

		return MIB12ConfigManager(self)

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

@context("MIB12ConfigManager")
class MIB12ConfigManager:
	def __init__(self, proxy):
		self.proxy = proxy

	def get_config_variable(self, index):
		metadata 	= self.proxy._read_appinfo_table(MIBConfigurationMetadataIndex, index)
		addresses 	= self.proxy._read_appinfo_table(MIBConfigurationAddressIndex, index)

		id, flags, length = struct.unpack("<HBB", metadata)
		ramloc,defaultloc = struct.unpack("<HH", addresses)

		var = {}
		var['id'] = id
		var['required'] = bool(flags & (1 << 6))
		var['index'] = flags & 0b00111111
		var['length'] = length
		var['address'] = ramloc
		var['default_value_adddress'] = defaultloc

		return var

	def get_config_variables(self):
		vars = {}
		for i in xrange(0, 100):
			var = self.get_config_variable(i)

			if var['length'] == 0xFF:
				break

			vars[var['id']] = var

		return vars

	@return_type("integer")
	def count_variables(self):
		"""
		Count the total number of configuration variables defined on this module
		"""
		vars = self.get_config_variables()
		return len(vars)

	@return_type("list(integer)")
	def list_variables(self):
		"""
		List the id numbers of all variables defined on this module
		"""

		vars = self.get_config_variables()

		return vars.keys()

	@return_type("list(string)")
	def describe_variables(self):
		"""
		Create a list of strings describing the defined config variables of this module
		"""

		vars = self.get_config_variables()
		out = []

		for var in vars.itervalues():
			reqstring = "optional"
			if var['required']:
				reqstring = 'required'

			curlen = self.proxy.readram(var['address'])

			desc = "0x%X: length (%d used of %d), %s" % (var['id'], curlen, var['length'], reqstring)
			out.append(desc)

		return out

	@param("id", "integer", desc="id of variable to set")
	@param("value", "string", desc="value to set in the variable")
	def set_string(self, id, value):
		"""
		Update variable with the given id to contain the string value passed in

		Value will not be null terminated, but the length will be prepended pascal-style
		"""

		for i in xrange(0, len(value), 16):
			chunk = value[i:i+16]
			res = self.proxy.rpc(0, 7, id, i, chunk)
			if res['return_value'] == 1:
				raise RPCError("Unknown configuration variable", id=id)
			elif res['return_value'] == 2:
				raise RPCError("Value is too long to fit inside variable, it may have only been partially updated", length=len(value))
