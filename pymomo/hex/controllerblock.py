#controllerblock.py
from pymomo.utilities.typedargs.types import *
from pymomo.exceptions import *
from pymomo.utilities.typedargs.annotate import *
from hexfile import HexFile

def print_validity(info):
	print "Validating Controller Metadata Block"

	magic = info['magic']
	if magic[0] == True:
		print "+ Valid magic number (0xBAAD, 0xDAAD)"
	else:
		print "- Invalid magic number: (0x%x, 0x%x)" % (magic[0], magic[1])

	firmware_length = info['firmware_end']
	if firmware_length[0] == True:
		print "+ Valid firmware length (0x%x)" % (firmware_length[1],)
	else:
		print "- Invalid firmware length (stored=0x%x, wanted=0x%x)" % (firmware_length[1], firmware_length[2])

	ivt = info['ivt_checksum']
	if ivt[0] == True:
		print "+ IVT checksum matches (0x%x)" % ivt[1]
	else:
		print "- IVT checksum mismatch (stored=0x%x, calculated=0x%x)" % (ivt[2], ivt[1])

	aivt = info['aivt_checksum']
	if aivt[0] == True:
		print "+ AIVT checksum matches (0x%x)" % aivt[1]
	else:
		print "- AIVT checksum mismatch (stored=0x%x, calculated=0x%x)" % (aivt[2], aivt[1])

	code = info['code_checksum']
	if code[0] == True:
		print "+ Program code checksum matches (0x%x)" % code[1]
	else:
		print "- Program code checksum mismatch (stored=0x%x, calculated=0x%x)" % (code[2], code[1])

	block = info['block_checksum']
	if block[0] == True:
		print "+ Metadata block checksum matches (0x%x)" % block[1]
	else:
		print "- Metadata block checksum mismatch (stored=0x%x, calculated=0x%x)" % (block[2], block[1])

	if info['valid']:
		print "\n**Metadata Block is valid**\n"
	else:
		print "\n**Metadata Block is invalid**\n"


@context("ControllerBlock")
class ControllerBlock:
	"""
	The metadata block in a pic24 controller firmware image.  This includes
	data like the specific hardware version that the controller is compiled
	for as well as checksums for various parts of the image that allow the
	controller board's bootloader to verify that the firmware image is valid
	and complete.
	"""

	firmware_length = 0xA600

	@param("source", "path", "readable", desc="hex file to load")
	def __init__(self, source):
		self.hex = HexFile(source, 24, 4, 2)
		self._parse_block()

	def _calculate_checksum(self, start, length):
		checksum = 0

		for i in xrange(start, start+length, 2):
			checksum += ((self.hex[i] >> 16) + self.hex[i])

		return ((~checksum) + 1) & 0xFFFF

	def _parse_block(self):
		base = 0x200
		self.magic = (self.hex[base+0], self.hex[base+2])
		self.reset = (self.hex[base+4], self.hex[base+6])
		self.firmware_end = self.hex[base+8]

		self.hw_version = ""
		for i in xrange(10, 10+8, 2):
			val = self.hex[base+i]
			low = val & 0xFF
			high = val >> 8 & 0xFF
			self.hw_version += chr(low)
			self.hw_version += chr(high)

		self.ivt_checksum = self.hex[base+18]
		self.aivt_checksum = self.hex[base+20]
		self.code_checksum = self.hex[base+22]
		self.block_checksum = self.hex[base+30]

	def _write_block(self):
		base = 0x200
		self.hex[base+0] = self.magic[0]
		self.hex[base+2] = self.magic[1]
		
		self.hex[base+4] = self.reset[0]
		self.hex[base+6] = self.reset[1]

		self.hex[base+8] = self.firmware_end

		for i in xrange(0, 8, 2):
			if i < (len(self.hw_version)-1):
				low = ord(self.hw_version[ i+ 0])
				high = ord(self.hw_version[i+ 1])
			elif i < len(self.hw_version):
				low = ord(self.hw_version[i])
				high = ord(' ')
			else:
				low = ord(' ')
				high = ord(' ')

			word = ((high & 0xFF) << 8) | (low & 0xFF)
			self.hex[base + 10 + i] = word

		self.hex[base+18] = self.ivt_checksum
		self.hex[base+20] = self.aivt_checksum
		self.hex[base+22] = self.code_checksum
		for i in xrange(24, 30, 2):
			self.hex[base+i] = 0

		self.hex[base+30] = self._calculate_checksum(0x200, 30)

	@param("dest", "path", "writeable", desc="output hex file path")
	def save(self, dest):
		"""
		Save the hexfile with a potentially updated metadata block
		into the path specified by dest.
		"""

		self._write_block()
		self.hex.save(dest)

	@annotated
	def update_checksums(self):
		"""
		Calculate the correct checksums that should be stored in the metadata block
		and add them to the in-memory copy of the block.
		"""

		self.ivt_checksum 	= self._calculate_checksum(0x04, 0x100 - 0x04)
		self.aivt_checksum	= self._calculate_checksum(0x100, 0x100)
		self.code_checksum	= self._calculate_checksum(0x200 + 32, ControllerBlock.firmware_length - 32)
		self.block_checksum = self._calculate_checksum(0x200, 30)

	@returns('HW Compatibility Version')
	def get_hw_version(self):
		return self.hw_version

	@param("hw", "string", desc="a string up to 16 bytes long")
	def set_hw_version(self, hw):
		"""
		Set the embedded hw compatibility string for this metadata block.  This is an
		ASCII string up to 16 bytes in length not including the terminating NULL.  It 
		is checked upon bootup against the hardcoded hw_version stored in the mainboard
		bootloader and if it does not match the controller hex file is not executed.
		"""

		if len(hw) > 16:
			hw = hw[:16]

		self.hw_version = hw

	@returns("Controller Block Status", printer=print_validity)
	def validate(self):
		"""
		Validate the data contained in this metadata block.
		"""

		status = {}
		status['magic'] = self._validate_magic()
		status['firmware_end'] 	= self._validate_firmware_length()
		status['ivt_checksum'] 	= self._validate_firmware_region(0x04, 0x100 - 0x04, self.ivt_checksum)
		status['aivt_checksum']	= self._validate_firmware_region(0x100, 0x100, self.aivt_checksum)
		status['code_checksum']	= self._validate_firmware_region(0x200 + 32, ControllerBlock.firmware_length - 32, self.code_checksum)
		status['block_checksum']= self._validate_firmware_region(0x200, 30, self.block_checksum)

		valid = reduce(lambda x,y: x and y, map(lambda x: x[0], status.itervalues()), True)
		status['valid'] = valid
		return status

	def _validate_magic(self):
		if self.magic[0] == 0xBAAD and self.magic[1] == 0xDAAD:
			return (True, self.magic[0], self.magic[1])
		else:
			return (False, self.magic[0], self.magic[1])

	def _validate_firmware_length(self):
		if self.firmware_end == ControllerBlock.firmware_length:
			return (True, self.firmware_end)

		return (False, self.firmware_end, ControllerBlock.firmware_length)

	def _validate_firmware_region(self, start, length, comp):
		check = self._calculate_checksum(start, length)
		if comp == check:
			return (True, check, comp)

		return (False, check, comp)

