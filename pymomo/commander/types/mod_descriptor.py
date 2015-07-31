from pymomo.commander.exceptions import *
import struct

class ModuleDescriptor:
	"""
	A structure holding information about a MIB module
	"""

	def __init__(self, buffer, addr):
		if len(buffer) != 11:
			raise TypeError('ModuleDescriptor', 'Length should have been 11, was %d' % len(buffer))

		hw_type, mod_type, info, name, reserved, feat_cnt = struct.unpack('BBB6sBB', buffer)

		self.hw = hw_type
		self.type = mod_type
		self.mib_revision = info & 0x0F
		self.flags = info >> 4
		self.name = name
		self.num_features = feat_cnt
		self.address = addr

		if len(self.name) > 6:
			self.name = self.name[0:6]