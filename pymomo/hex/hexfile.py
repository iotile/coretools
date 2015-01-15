#hexfile.py

import intelhex
from pymomo.utilities.typedargs.types import *
from pymomo.exceptions import *
from pymomo.utilities.typedargs.annotate import *

def print_ranges(ranges):
	print "Defined Address Ranges"
	for start,stop in ranges:
		print "[0x%X, 0x%X]" % (start, stop) 

def print_errors(errors):
	print "Comparing hex files"

	if len(errors) == 0:
		print "Files are equivalent"
		return

	for error in errors:
		src = 'first'
		this = error['this']
		other = error['other']
		if error['direction'] == 'reverse':
			src = 'second'
			this = error['other']
			other = error['this']

		print "Mismatch in range (0x%X, 0x%X) defined in %s file, file 1: 0x%X, file 2: 0x%X @ address 0x%x" % (error['range'][0], error['range'][1], src, this, other, error['address'])

@context("HexFile")
class HexFile(object):
	"""
	A generalized container object for representing sparse memory views like those
	contained in intel HEX files.  It uses the intelhex format for reading hex files
	but contains the ability to modify the read information to acount for symantic
	details like word size and default padding.  It's primary purpose is to support
	pic12 and pic24 hex files which have 14-bit and 24-bit words respectively.
	"""

	@param("source", "path", "readable", desc="hex file to load")
	@param("wordsize", "integer", "positive", desc="native word size of architecture in bits")
	@param("filewords", "integer", "positive", desc="bytes per word in hex file")
	@param("skip", "integer", "positive", desc="valid addresses: 1=all, 2=even")
	@param("cutoff", "integer", "positive", desc="ignore addresses above this value")
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

	def _convert_to_hex(self):
		"""
		Convert from a native word representation to a padded hex file
		using the parameters specified upon creation of this HexFile object
		"""

		ih = intelhex.IntelHex()

		addrs = self.addresses()
		mask = (1 << self.wordsize) -1

		for addr in addrs:
			start = (addr/self.skip) * self.filewords

			val = self._buf[addr] & mask

			for i in xrange(0, self.filewords):
				byte_i = (val >> (8*i)) & 0xFF
				ih[start + i] = byte_i

		return ih

	def addresses(self):
		return sorted(self._buf.keys())

	def __getitem__(self, x):
		if x in self._buf:
			return self._buf[x]

		return self.fill

	def __setitem__(self, x, val):
		self._buf[x] = val

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

	@param("dest", "path", "writeable", desc='path of output file to create')
	def save(self, dest):
		"""
		Save a copy of the current state of this hexfile to the path specified
		by dest.
		"""

		ih = self._convert_to_hex()
		ih.write_hex_file(dest)

	@param("other", "path", "readable", desc="Other hex file to compare to this one")
	@param("type", "string", ("list", ("oneway, twoway")), desc="compare in both directions")
	@returns("list of mismatches", printer=print_errors, data=True)
	def compare(self, other, type="oneway"):
		"""
		Load another hex file from the given path and compare it to this one.  If type is
		oneway, then only consider the address ranges defined in this file, so the files
		compare as the same if all addresses defined in this HexFile agree with the values
		in the other hex file.  If type is twoway, the comparison is repeated for all address
		ranges defined in the other file as well.
		"""

		if not isinstance(other, HexFile):
			other = HexFile(other, self.wordsize, self.filewords, self.skip, self.cutoff)

		ownranges = self.ranges()

		errors = []

		for r in ownranges:
			for i in xrange(r[0], r[1]+1):
				sval = self[i]
				oval = other[i]

				if sval != oval:
					err = {"range": r, "address": i, "this": sval, "other": oval, "direction": "forward"}
					errors.append(err)
					break

		#if we're asked for a two-way comparison, also compare the other direction
		if type == "twoway":
			rev_errors = other.compare(self)
			for err in rev_errors:
				err['direction'] = 'reverse'

			errors.extend(rev_errors)

		return errors