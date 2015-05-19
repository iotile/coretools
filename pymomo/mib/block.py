#block.py
#An object representing a MIBBlock

from handler import MIBHandler
import sys
import os.path
from pymomo.utilities import build, template
from pymomo.hex8.decode import *
from pymomo.utilities import intelhex
from pymomo.exceptions import *
from config12 import MIB12Processor

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
	2: "12lf1822",
	3: "16lf1823",
	4: "16lf1847"
}

class MIBBlock:
	"""
	The block in program memory describing a MoMo application module.  The MIB block
	contains information on the application module and a sparse matrix representation
	of a jump table containing all of the command ids and interfaces that the module 
	knows how to respond to.
	"""

	TemplateName = 'command_map.asm'

	def __init__(self, ih=None):
		"""
		Given an intelhex object, extract the MIB block information
		from it or raise an exception if a MIBBlock cannot be found
		at the right location.
		"""

		build_settings = build.load_settings()

		self.base_addr = build_settings["mib12"]["mib"]["base_address"]
		self.curr_version = build_settings["mib12"]["mib"]["current_version"]
		self.commands = {}
		self.interfaces = []

		self.valid = True
		self.error_msg = ""
		self.hw_type = -1

		if isinstance(ih, basestring):
			ih = intelhex.IntelHex16bit(ih)
			ih.padding = 0x3FFF

		if ih is not None:
			try:
				self._load_from_hex(ih)
			except ValueError as e:
				self.error_msg = e
				self.valid = False

		self._parse_hwtype()

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
		Add a command to the MIBBlock.  

		The cmd_id must be a non-negative 2 byte number.
		handler should be the command handler
		"""

		if cmd_id < 0 or cmd_id >= 2**16:
			raise ArgumentError("Command ID in mib block is not a non-negative 2-byte number", cmd_id=cmd_id, handler=handler)

		if cmd_id in self.commands:
			raise ArgumentError("Attempted to add the same command ID twice.", cmd_id=cmd_id, existing_handler=self.commands[cmd_id],
								new_handler=handler)

		self.commands[cmd_id] = handler

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

	def _load_from_hex(self, ih):
		if not self._check_magic(ih):
			raise ValueError("Invalid magic number.")

		app_info_table_addr = decode_goto(ih, self.base_addr + app_information_offset) + 1 # table contains andlw as the first instruction so get past that
		
		app_info_table = decode_table(ih ,app_info_table_addr, decode_goto)

		cmd_list_addr = decode_fsr0_loader(ih, app_info_table[cmd_map_index])
		interfaces_list_addr = decode_fsr0_loader(ih, app_info_table[interface_list_index])

		#Strip off the high bits indicating program memmory addresses
		cmd_list_addr = self._convert_program_address(cmd_list_addr)
		interfaces_list_addr = self._convert_program_address(interfaces_list_addr)

		cmd_table = decode_sentinel_table(ih, cmd_list_addr, 4, [0xFF, 0xFF, 0xFF, 0xFF])
		iface_table = decode_sentinel_table(ih, interfaces_list_addr, 4, [0xFF, 0xFF, 0xFF, 0xFF])

		#Decode and add the commands to our command map
		for entry in cmd_table:
			cmd_id = entry[0] | (entry[1] << 8)
			cmd_addr = entry[2] | (entry[3] << 8)

			self.add_command(cmd_id, MIBHandler(address=cmd_addr))

		#Decode and add the interfaces to our interface list
		for entry in iface_table:
			iface_id = entry[0] | (entry[1] << 8) | (entry[2] << 16) | (entry[3] << 24)
			self.add_interface(iface_id)

		self.name = decode_string(ih, self.base_addr + name_offset, 6)

		self.hw_type = decode_retlw(ih, self.base_addr + hw_offset)
		self._parse_hwtype()

		api_major = decode_retlw(ih, self.base_addr + major_api_offset)
		api_minor = decode_retlw(ih, self.base_addr + minor_api_offset)
		self.set_api_version(api_major, api_minor)

		mod_major = decode_retlw(ih, self.base_addr + major_version_offset)
		mod_minor = decode_retlw(ih, self.base_addr + minor_version_offset)
		mod_patch = decode_retlw(ih, self.base_addr + patch_version_offset)
		self.set_module_version(mod_major, mod_minor, mod_patch)

		self.stored_checksum = decode_retlw(ih, self.base_addr + checksum_offset)
		self.app_checksum = self._calculate_app_checksum(ih)

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

	def create_asm(self, folder):
		temp = template.RecursiveTemplate(MIBBlock.TemplateName)
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