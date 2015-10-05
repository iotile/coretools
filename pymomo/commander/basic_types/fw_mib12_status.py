import struct
import pymomo.mib.block

class MIB12ExecutiveStatus:
	def __init__(self, buf):
		if len(buf) != size():
			raise ValueError("Invalid length, expected %d got %d" % (size(), len(buf)))

		major, minor, hw, status = struct.unpack("<BBBB", buf)

		self.api_major = major
		self.api_minor = minor
		self.hardware_type = hw

		#Process the status register
		self.application_running = False
		self.trapped = False
		self.valid_application = False

		if status & (1 << 1):
			self.valid_application = True

		if status & (1 << 4):
			self.application_running = True

		if status & (1 << 7):
			self.trapped = True

	def hardware_id(self):
		return self.hardware_type

	def hardware_name(self):
		return pymomo.mib.block.known_hwtypes.get(self.hardware_type, "unknown (type=%d)" % self.hardware_type)

	def __str__(self):
		return default_formatter(self)

def size():
	return 4

def convert(arg):
	return MIB12ExecutiveStatus(arg)

#Formatting Functions
def default_formatter(arg, **kwargs):
	out = "MIB12 Executive Status\n"
	out += "API Version: %d.%d\n" % (arg.api_major, arg.api_minor)
	out += "Hardware Type: %s\n" % arg.hardware_name()
	out += "Valid Application Loaded: %s\n" % str(arg.valid_application)
	out += "Application Code Allowed: %s\n" % str(arg.application_running)
	out += "Trapped: %s" % str(arg.trapped)
	return out