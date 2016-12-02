# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#block.py
#An object representing a TBBlock

from handler import TBHandler
import sys
import os.path
from iotile.build.utilities import template
from iotile.build.build import build
from iotile.core.utilities import intelhex
from iotile.core.exceptions import *
from pkg_resources import resource_filename, Requirement

block_size = 16

hw_offset = 0
major_api_offset = 1
minor_api_offset = 2
name_offset = 3
major_version_offset = 9
minor_version_offset = 10
patch_version_offset = 11
checksum_offset = 12
magic_offset = 13
app_information_offset = 14
reserved = 15

# Indices into the app_information_table
cmd_map_index = 0
interface_list_index = 1
config_list_index = 2
reserved_index = 3

known_hwtypes = {
	10: "NXP LPC824 (Cortex M0+)"
}

class TBBlock:
	"""
	The block in program memory describing a MoMo application module.  The MIB block
	contains information on the application module and a sparse matrix representation
	of a jump table containing all of the command ids and interfaces that the module 
	knows how to respond to.
	"""

	TemplateName 				= 'command_map.asm'
	CTemplateName 				= 'command_map_c.c'
	CTemplateNameHeader 		= 'command_map_c.h'
	ConfigTemplateName			= 'config_variables_c.c'
	ConfigTemplateNameHeader	= 'config_variables_c.h'
	
	def __init__(self):
		"""
		Given an intelhex object, extract the MIB block information
		from it or raise an exception if a TBBlock cannot be found
		at the right location.
		"""

		self.commands = {}
		self.configs = {}
		self.interfaces = []

		self.valid = True
		self.error_msg = ""
		self.hw_type = -1

		self._parse_hwtype()

	@classmethod
	def ParseHardwareType(cls, ih):
		if isinstance(ih, basestring):
			ih = intelhex.IntelHex16bit(ih)
			ih.padding = 0x3FFF

		if ih is None:
			raise ArgumentError("Could not load intelhex file from arguement", argument=strih)

		build_settings = build.load_settings()
		base_addr = build_settings["mib12"]["mib"]["base_address"]
		hw_type = decode_retlw(ih, base_addr + hw_offset)
		
		if hw_type in known_hwtypes:
			return known_hwtypes[hw_type]

		raise DataError("Unknown Hardware Type", hw_type=hw_type)

	def set_api_version(self, major, minor):
		"""
		Set the API version this module was designed for.

		Each module must declare the mib12 API version it was compiled with as a
		2 byte major.minor number.  This information is used by the pic12_executive
		to decide whether the application is compatible.
		"""

		if major > 255 or major < 0 or minor > 255 or minor < 0:
			raise ArgumentError("Invalid API version number with component that does not fit in 1 byte", major=major, minor=minor)
		
		self.api_version = (major, minor)

	def set_module_version(self, major, minor, patch):
		"""
		Set the module version for this module.

		Each module must declare a semantic version number in the form:
		major.minor.patch

		where each component is a 1 byte number between 0 and 255.
		"""

		if major > 255 or major < 0 or minor > 255 or minor < 0 or patch > 255 or patch < 0:
			raise ArgumentError("Invalid module version number with component that does not fit in 1 byte", major=major, minor=minor, patch=patch)

		self.module_version = (major, minor, patch)

	def set_name(self, name):
		"""
		Set the module name to a 6 byte string

		If the string is too short it is appended with space characters.
		"""

		if len(name) > 6:
			raise ArgumentError("Name must be at most 6 characters long", name=name)

		if len(name) < 6:
			name += ' '*(6 - len(name))

		self.name = name

	def add_interface(self, interface):
		"""
		Add an interface to the MIB Block.

		The interface must be a number between 0 and 2^32 - 1, i.e. a non-negative 4 byte integer 
		"""

		if interface < 0 or interface >= 2**32:
			raise ArgumentError("Interface ID is not a non-negative 4-byte number", interface=interface)

		if interface in self.interfaces:
			raise ArgumentError("Attempted to add the same interface twice.", interface=interface, existing_interfaces=self.interfaces)

		self.interfaces.append(interface)

	def add_command(self, cmd_id, handler):
		"""
		Add a command to the TBBlock.  

		The cmd_id must be a non-negative 2 byte number.
		handler should be the command handler
		"""

		if cmd_id < 0 or cmd_id >= 2**16:
			raise ArgumentError("Command ID in mib block is not a non-negative 2-byte number", cmd_id=cmd_id, handler=handler)

		if cmd_id in self.commands:
			raise ArgumentError("Attempted to add the same command ID twice.", cmd_id=cmd_id, existing_handler=self.commands[cmd_id],
								new_handler=handler)

		self.commands[cmd_id] = handler

	def add_config(self, config_id, config_data):
		"""
		Add a configuration variable to the MIB block
		"""

		if config_id < 0 or config_id >= 2**16:
			raise ArgumentError("Config ID in mib block is not a non-negative 2-byte number", config_data=config_id, data=config_data)

		if config_id in self.configs:
			raise ArgumentError("Attempted to add the same command ID twice.", config_data=config_id, old_data=self.configs[config_id],
								new_data=config_data)

		self.configs[config_id] = config_data

	def _check_magic(self, ih):
		magic_addr = self.base_addr + magic_offset
		instr = ih[magic_addr]

		#Magic Value should be a retlw 0xAA
		if instr == 0x34AA:
			return True

		return False

	def _convert_program_address(self, addr):
		"""
		Make sure that addr points to program memory (by having the high bit set) 
		and then strip the high bit
		"""

		if not addr & (1 << 15):
			raise ValueError("Address 0x%X did not have the high bit set indicating a program memory address." % addr)

		return addr & ~(1 << 15)

	def _calculate_app_checksum(self, ih):
		"""
		Calculate the checksum of the application module.

		Automatically find the correct start and stop rows based on the information for this
		hardware type.
		"""

		proc = MIB12Processor.FromChip(self.chip_name)

		start,stop = proc.app_rom

		check = 0
		for i in xrange(start, stop+1):
			low = ih[i] & 0xFF
			high = ih[i] >> 8
			high = high & 0b00111111
			check += low + high

		check = check & 0xFF
		return check

	def _parse_hwtype(self):
		"""
		Convert the numerical hw id to a chip name using the well-known
		conversion table
		"""

		if self.hw_type not in known_hwtypes:
			self.chip_name = "Unknown Chip (type=%d)" % self.hw_type
			return

		self.chip_name = known_hwtypes[self.hw_type]

	def create_c(self, folder):
		"""
		Create a C file that contains a map of all of the mib commands defined in this block

		Also create config files containing definitions for all of the required config variables. 
		"""

		temp = template.RecursiveTemplate(TBBlock.CTemplateName, resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
		temp.add(self)
		temp.render(folder)

		temp = template.RecursiveTemplate(TBBlock.ConfigTemplateName, resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
		temp.add(self)
		temp.render(folder)

		temp = template.RecursiveTemplate(TBBlock.CTemplateNameHeader, resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
		temp.add(self)
		temp.render(folder)

		self.create_config_headers(folder)

	def create_config_headers(self, folder):
		"""
		Create C headers for config variables defined in this block
		"""

		temp = template.RecursiveTemplate(TBBlock.ConfigTemplateNameHeader, resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
		temp.add(self)
		temp.render(folder)

	def __str__(self):
		rep  = "MIB Block\n"
		rep += "---------\n"

		if not self.valid:
			rep += "Block invalid: %s\n" % self.error_msg
			return rep

		rep += "Block Valid\n"
		rep += "Name: '%s'\n" % self.name
		rep += "Hardware: %s\n" % self.chip_name
		rep += "API Version: %d.%d\n" % (self.api_version[0], self.api_version[1])
		rep += "Module Version: %d.%d.%d\n" % (self.module_version[0], self.module_version[1], self.module_version[2])

		if hasattr(self, 'stored_checksum'):
			rep += "Stored Checksum: 0x%X\n" % self.stored_checksum
			rep += "Checksum Valid: %s" % (self.app_checksum == 0,)
		else:
			rep += "Checksum Valid: Unknown" 

		rep += "\n# Supported Commands #"
		for id, handler in self.commands.iteritems():
			rep += "\n0x%X: %s" % (id, str(handler))

		rep += "\n\n# Supported Interfaces #"
		for id in self.interfaces:
			rep += "\n0x%X" % id

		return rep