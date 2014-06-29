#hexfile.py

import intelhex
from pymomo.utilities.typedargs.types import *
from pymomo.utilities.typedargs.exceptions import *
from pymomo.utilities.typedargs.annotate import *

def print_ranges(ranges):
	print "Defined Address Ranges"
	for start,stop in ranges:
		print "[0x%X, 0x%X]" % (start, stop) 

class HexFile(object):
	"""
	A generalized container object for representing sparse memory views like those
	contained in intel HEX files.  It uses the intelhex format for reading hex files
	but contains the ability to modify the read information to acount for symantic
	details like word size and default padding.  It's primary purpose is to support
	pic12 and pic24 hex files which have 14-bit and 24-bit words respectively.
	"""

	@param("source", "path", "readable", description="hex file to load")
	@param("wordsize", "integer", "positive", description="native word size of architecture in bits")
	@param("filewords", "integer", "positive", description="bytes per word in hex file")
	@param("skip", "integer", "positive", description="valid addresses: 1=all, 2=even")
	@param("cutoff", "integer", "positive", description="ignore addresses above this value")
	def __init__(self, source, wordsize, filewords, skip=1, cutoff=0xFFFF):
		"""
		Create a HexFile object representing the source file 
		"""

		ih = intelhex.IntelHex(source)

		self.wordsize = wordsize
		self.filewords = filewords
		self.skip = skip
		self.fill = (1 << (self.wordsize)) - 1
		self.cutoff = cutoff
		self._buf = {}
		self._convert_from_hex(ih)

	def _read_word(self, ih, addr):
		"""
		Read filewords bytes from ih starting at addr.  Raise an error if some of
		the bytes are not implemented. 
		"""

		word = 0

		for i in xrange(0, self.filewords):
			a = addr+i
			if a not in ih._buf:
				print a
				raise InternalError("Hex file had incorrect word size at address %d" % addr)

			val = ih._buf[a]
			word |= (val & 0xFF) << (i*8)

		mask = (1 << self.wordsize) -1
		if word > mask:
			raise InternalError("Hex file had word exceeding the specified architecture word width (%d bits), value was %d @ address 0x%X" % (self.wordsize, word, addr))

		return word

	def _convert_from_hex(self, ih):
		"""
		Convert from a padded hex file to a native word representation
		"""

		start = ih.minaddr()
		end = ih.maxaddr()

		if start % self.filewords != 0:
			raise InternalError("Hex file did not start on a multiple of its file word size. (base address was %d, word size was %d" % (start, self.filewords))

		aligned_start = start / self.filewords

		for i in xrange(start, end, self.filewords):
			if i not in ih._buf or i>self.cutoff:
				continue

			addr = 	i/self.filewords * self.skip
			word = self._read_word(ih, i)
			self._buf[addr] = word

	def addresses(self):
		return sorted(self._buf.keys())

	@returns("list of defined address ranges", printer=print_ranges, data=True)
	def ranges(self):
		"""
		Get all of the consecutive ranges defined in this file as native
		addresses.
		"""

		valid_addr = self.addresses()
		rstart = valid_addr[0]

		ranges = []

		for i in xrange(1, len(valid_addr)):
			if valid_addr[i] != valid_addr[i-1] + self.skip:
				rend = valid_addr[i-1]
				ranges.append((rstart, rend))
				rstart = valid_addr[i]

		ranges.append((rstart, valid_addr[-1]))

		return ranges