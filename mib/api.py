#api.py
#Routines for dumping the MIB API region of a mib12 executive module and verifying
#the contents to make sure they have not been stomped on by some other process.

from pymomo.hex8.decode import *
from pymomo.utilities.paths import MomoPaths
from pymomo.utilities import build
from config12 import MIB12Processor
import intelhex

class MIBAPI:
	def __init__(self, hexfile, chip):
		with open(hexfile, "r"):
			self.hf = intelhex.IntelHex16bit(hexfile)

		proc = MIB12Processor.FromChip(chip)
		self.api_base = proc.api_range[0]

		self.valid = self.verify_api()

	def verify_api(self):
		"""
		Verify that all instructions in the MIB api region are either retlw 0
		or goto.
		"""
		for i in xrange(0, 16):
			try:
				val = decode_retlw(self.hf, self.api_base + i)
				if val == 0:
					continue

				return False
			except:
				pass

			try: 
				decode_goto(self.hf, self.api_base + i)
				continue
			except:
				pass

			return False

		return True

	def print_api(self):
		print "MIB API Block"
		print "Valid:", self.valid
		print "\nTable Contents Follow"

		for i in xrange(0, 16):
			try:
				val = decode_retlw(self.hf, self.api_base + i)
				print "%d: retlw 0x%x" % (i, val)
				continue
			except:
				pass

			try: 
				addr = decode_goto(self.hf, self.api_base + i)
				print "%d: goto 0x%x" % (i, addr)
				continue
			except:
				pass

			print "%d: Invalid Instruction (0x%x)" % (i, self.hf[self.api_base + i])
