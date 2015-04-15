#block.py
#An object representing a MIBBlock

from handler import MIBHandler
import sys
import os.path
from pymomo.utilities import build, template
from pymomo.hex8.decode import *
from pymomo.utilities import intelhex
from pymomo.exceptions import *

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
command_map_offset = 14
interface_map_offset = 15

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
		self.valid = True
		self.error_msg = ""

		if isinstance(ih, basestring):
			ih = intelhex.IntelHex16bit(ih)

		if ih is not None:
			try:
				self._load_from_hex(ih)
				self._check_consistency()
				self._interpret_handlers()
				self._build_command_map()
			except ValueError as e:
				self.error_msg = e
				self.valid = False

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

	def _interpret_handlers(self):
		self.handlers = map(lambda i: MIBHandler(self.spec_list[i], address=self.handler_addrs[i]), xrange(0, len(self.spec_list)))

	def _check_magic(self, ih):
		magic_addr = self.base_addr + magic_offset
		instr = ih[magic_addr]

		#Magic Value should be a retlw 0xAA
		if instr == 0x34AA:
			return True

		return False

	def _load_from_hex(self, ih):
		if not self._check_magic(ih):
			raise ValueError("Invalid magic number.")

		self.cmds_addr = decode_goto(ih, self.base_addr + command_map_offset)
		self.interfaces_addr = decode_goto(ih, self.base_addr + interface_map_offset)

		self.cmd_list = decode_table(ih, self.cmds_addr, decode_retlw)
		self.interface_list = decode_table(ih, self.interfaces_addr, decode_retlw)

		self.name = decode_string(ih, self.base_addr + name_offset, 7)
		self.hw_type = decode_retlw(ih, self.base_addr + hw_offset)

		#FIXME: Parse other items from the mib block

		self._parse_hwtype()

	def _parse_hwtype(self):
		"""
		Convert the numerical hw id to a chip name using the well-known
		conversion table
		"""

		if self.hw_type not in known_hwtypes:
			self.chip_name = "Unknown Chip (type=%d)" % self.hw_type

		self.chip_name = known_hwtypes[self.hw_type]

	def _check_consistency(self):
		self.valid = True
		#FIXME: Check to make sure that the cmd and interface lists end with a sentinel

	def create_asm(self, folder):
		temp = template.RecursiveTemplate(MIBBlock.TemplateName)
		temp.add(self)
		temp.render(folder)

	def __str__(self):
		rep = "\n"

		rep += "MIB Block\n"
		rep += "---------\n"

		if not self.valid:
			rep += "Block invalid: %s\n" % self.error_msg
			return rep

		rep += "Block Valid\n"
		rep += "Name: '%s'\n" % self.name
		rep += "Type: %d\n" % self.module_type
		rep += "Hardware: %s\n" % self.chip_name
		rep += "MIB Revision: %d\n" % self.revision
		rep += "Flags: %s\n" % bin(self.flags)
		rep += "Number of Features: %d\n" % self.num_features

		rep += "\nFeature List\n"



		for f in self.features.keys():
			rep += "%d:\n" % f
			for i,h in enumerate(self.features[f]):
				rep += "    %d: %s\n" % (i, str(h))

		return rep