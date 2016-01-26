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
		return (res['buffer'][0])

	@annotated
	def reset(self):
		"""
		Reset the application module.
		"""

		try:
			self.rpc(0, 1)
		except ModuleNotFoundError:
			pass
	
	def _read_appinfo_table(self, table, offset):
		"""
		Read a single entry from the application info table specified by table
		"""

		res = self.rpc(0, 2, int(table), int(offset)*4, result_type=(0, True))

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

			if (iface[0]) == 0xFF and (iface[1]) == 0xFF and (iface[2]) == 0xFF and (iface[3]) == 0xFF:
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


@context("MIB12ConfigManager")
class MIB12ConfigManager:
	def __init__(self, proxy):
		self._proxy = proxy

	@param("index", "integer", desc="index of variable to get")
	@return_type("map(string, integer)")
	def get_config_variable(self, index):
		metadata 	= self._proxy._read_appinfo_table(MIBConfigurationMetadataIndex, index)
		addresses 	= self._proxy._read_appinfo_table(MIBConfigurationAddressIndex, index)

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

			curlen = self._proxy.readram(var['address'])

			desc = "0x%X: %d byte(s) used of %d byte(s) allocated, %s" % (var['id'], curlen, var['length'], reqstring)
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
			res = self._proxy.rpc(0, 7, id, i, chunk)
			if res['return_value'] == 1:
				raise RPCError("Unknown configuration variable", id=id)
			elif res['return_value'] == 2:
				raise RPCError("Value is too long to fit inside variable, it may have only been partially updated", length=len(value))
