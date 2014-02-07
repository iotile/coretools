#block.py
#An object representing a MIBBlock

from handler import MIBHandler
import sys
import os.path
from pymomo.utilities import build, template
from pymomo.hex8.decode import *
import intelhex

block_size = 16

hw_offset = 0
type_offset = 1
info_offset = 2
name_offset = 3
num_feature_offset = 10
features_offset = 11
cmds_offset = 12
specs_offset = 13
handlers_offset = 14
magic_offset = 15

known_hwtypes = {
	2: "12lf1822",
	3: "16lf1823",
	4: "16lf1847"
}

class MIBBlock:
	"""
	The block in program memory describing a MoMo application module.  The MIB block
	contains information on the application module and a sparse matrix representation
	of a jump table containing all of the feature, command combinations that the 
	module knows how to respond to.
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
		self.features = {}
		self.valid = True
		self.error_msg = ""
		self.num_features = 0

		if isinstance(ih, basestring):
			ih = intelhex.IntelHex16bit(ih)

		if ih is not None:
			try:
				self._load_from_hex(ih)
				self._check_consistency()
				self._interpret_handlers()
				self._build_feature_map()
			except ValueError as e:
				self.error_msg = e
				self.valid = False

	def set_variables(self, name, type, flags):
		self.name = name
		self.flags = flags
		self.module_type = type

	def add_command(self, feature, cmd, handler):
		"""
		Add a command to the MIBBlock.  The cmd must be sequential after
		the last command in the feature that it is added to, i.e. you must add
		feature 1, cmd 0 before adding feature 1 cmd 1.
		"""

		if feature not in self.features:
			self.features[feature] = []
			self.num_features = len(self.features.keys())

		if cmd != len(self.features[feature]):
			raise ValueError("Added noncontiguous command %d (%s) to feature %d, last command was %d" % (cmd, handler.symbol, feature, len(self.features[feature])))

		self.features[feature].append(handler)

	def _interpret_handlers(self):
		self.handlers = map(lambda i: MIBHandler(self.spec_list[i], address=self.handler_addrs[i]), xrange(0, len(self.spec_list)))

	def _build_feature_map(self):
		cmd_i  = 0

		self.features = {}
		for i in xrange(0, len(self.feature_list)):
			self.features[self.feature_list[i]] = []
			for j in xrange(self.cmd_list[i], self.cmd_list[i+1]):
				self.features[self.feature_list[i]].append(self.handlers[cmd_i])

				cmd_i += 1

	def _check_magic(self, ih):
		magic_addr = self.base_addr + magic_offset
		instr = ih[magic_addr]

		#Last instruction should be retlw 0xAA for the magic number
		if instr == 0x34AA:
			return True

		return False

	def _check_consistency(self):
		"""
		Check that the features, commands, handlers, and specifications are mutually consistent
		"""

		self.valid = False

		if self.num_features != len(self.feature_list):
			raise ValueError("Mismatch between length of feature list and num_features.")

		if len(self.cmd_list) != len(self.feature_list)+1:
			raise ValueError("Command list has wrong number of entries, was %d, should be %d" % (len(cmds), len(features)+1))

		if len(self.spec_list) != len(self.handler_addrs):
			raise ValueError("There should be a 1-1 mapping between command specs and handlers. Their lengths differed (specs: %d, handlers: %d)." % (len(self.specs), len(self.handler_addrs)))

		if len(self.handler_addrs) != self.cmd_list[-1]:
			raise ValueError("Command array has invalid format.  Last entry should be the number of total handlers (total handlers: %d, cmd entry: %d)" % (len(self.handler_addrs), self.cmds[-1]))

		self.valid = True

	def _load_from_hex(self, ih):
		if not self._check_magic(ih):
			raise ValueError("Invalid magic number.")

		self.num_features = decode_retlw(ih, self.base_addr + num_feature_offset)
		self.features_addr = decode_goto(ih, self.base_addr + features_offset)
		self.cmds_addr = decode_goto(ih, self.base_addr + cmds_offset)
		self.specs_addr = decode_goto(ih, self.base_addr + specs_offset)
		self.handlers_addr = decode_goto(ih, self.base_addr + handlers_offset)

		self.feature_list = decode_table(ih, self.features_addr, decode_retlw)
		self.cmd_list = decode_table(ih, self.cmds_addr, decode_retlw)
		self.spec_list = decode_table(ih, self.specs_addr, decode_retlw)
		self.handler_addrs = decode_table(ih, self.handlers_addr, decode_goto)

		self.name = decode_string(ih, self.base_addr + name_offset, 7)
		self.hw_type = decode_retlw(ih, self.base_addr + hw_offset)
		self.info = decode_retlw(ih, self.base_addr + info_offset)
		self.module_type = decode_retlw(ih, self.base_addr + type_offset)

		self.revision = self.info >> 4
		self.flags = self.info & 0x0F

		self._parse_hwtype()

	def _parse_hwtype(self):
		"""
		Convert the numerical hw id to a chip name using the well-known
		conversion table
		"""

		if self.hw_type not in known_hwtypes:
			self.chip_name = "Unknown Chip (type=%d)" % self.hw_type

		self.chip_name = known_hwtypes[self.hw_type]


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