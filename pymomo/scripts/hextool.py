#!/usr/bin/env python

import sys
import os.path
import os
import intelhex

import cmdln
from colorama import Fore, Style
from pymomo.hex8.instruction import Instruction
from pymomo.hex8 import merge
from pymomo.hex8.ranges import *

class HexTool(cmdln.Cmdln):
	name = 'hextool'

	@cmdln.option('-o', '--output', action='store',  help='output hex file')
	@cmdln.option('-a', '--addr', action='store', help="the address to patch")
	@cmdln.option('-v', '--verify', action='store', default=None, help="verify the previous contents before patching")
	@cmdln.option('-r', '--replace', action='store')
	@cmdln.option("-p", '--pic24', action="store_true", default=False, help='Is the hex file for a 16 bit PIC' )
	def do_patch(self, subcmd, opts, hexfile):
		"""${cmd_name}: patch a 16 bit pic12 or pic16 hex file

		Replace the instruction at address --addr with the instruction
		given by --replace.  Save the patched file in --output and optionally
		verify that the previous contents at --addr were --verify.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['addr', 'output', 'replace'])
		verify = None
		addr = self.parse_num(opts.addr)

		#Do the patching
		ih = self.load_ih(hexfile, pic24=opts.pic24)

		if opts.pic24 == False:
			repl = self.parse_instr(opts.replace)
			if opts.verify is not None:
				verify = self.parse_instr(opts.verify)

			if verify is not None:
				op = verify.encode()
				if ih[addr] != op:
					self.error("Verification failed, old address contents: 0x%X, expected 0x%X for '%s'" % (ih[addr], op, str(verify.op)))

			print "Replacing Instruction at 0x%X with %s" % (addr, repl.op)
			ih[addr] = repl.encode()
		else:
			repl = self.parse_num(opts.replace)
			print "Replacing 0x%X at address 0x%X with 0x%X" % (ih[addr*2], addr, repl)
			ih[addr*2] = repl

		ih.write_hex_file(opts.output)

	@cmdln.option('-o', '--output', action='store',  help='output hex file')
	@cmdln.option('-a', '--addr', action='store', help="the address to start inserting")
	@cmdln.option('-s', '--skip', action='append', help="skip address range inclusive: start,end")
	@cmdln.option('-m', '--maxsize', action='store', default='0', help="the maximum size to insert")
	def do_insert(self, subcmd, opts, stub_file, payload_file):
		"""${cmd_name}: merge payload into stub at a given offset

		Write the hex file specified by payload sequentially into the
		address space of stub starting at addr and optionally skipping
		address ranges specified with --skip.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['output', 'addr'])
		stub = self.load_ih(stub_file)
		payload = self.load_ih(payload_file)

		#Write payload into stub starting at write_addr
		#and skipping over the ranges listed in skip_ranges
		skip_ranges = self.parse_ranges(opts.skip)
		write_addr = self.parse_num(opts.addr)
		max_size = self.parse_num(opts.maxsize)

		print "Inserting hex file at address: 0x%X" % write_addr

		merge.insert_hex(stub, payload, write_addr, skip_ranges, max_size)
		stub.write_hex_file(opts.output)

	@cmdln.option('-o', '--output', action='store',  help='output hex file')
	@cmdln.option('-a', '--addr', action='store', help="the address to start extracting")
	@cmdln.option('-s', '--skip', action='append', help="skip address range inclusive: start,end")
	@cmdln.option('-m', '--maxsize', action='store', default='0', help="the maximum size to extract")
	def do_extract(self, subcmd, opts, hexfile):
		"""${cmd_name}: merge payload into stub at a given offset

		Write the hex file specified by payload sequentially into the
		address space of stub starting at addr and optionally skipping
		address ranges specified with --skip.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['output', 'addr'])
		stub = self.load_ih(hexfile)

		#Write payload into stub starting at write_addr
		#and skipping over the ranges listed in skip_ranges
		skip_ranges = self.parse_ranges(opts.skip)
		write_addr = self.parse_num(opts.addr)
		max_size = self.parse_num(opts.maxsize)

		print "Extracting hex file at address: 0x%X" % write_addr

		out = merge.extract_hex(stub, write_addr, skip_ranges, max_size)
		out.write_hex_file(opts.output)

	def do_merge(self, subcmd, opts, file1, file2, file3):
		"""${cmd_name}: merge two pic24 hex files together

		Combine file1 and file2, where the contents of file2 overlap the contents of file1,
		file2 will overwrite file1.  The result is saved into file3
		
		${cmd_usage}
		${cmd_option_list}
		"""

		ih1 = intelhex.IntelHex(file1)
		ih2 = intelhex.IntelHex(file2)

		ih1.merge(ih2, overlap='replace')
		ih1.write_hex_file(file3)

	@cmdln.option("-p", '--pic24', action="store_true", default=False, help='Is the hex file for a 16 bit PIC' )
	def do_compare(self, subcmd, opts, file1, file2):
		"""${cmd_name}: compare file1 and file2 

		Compare the contents of file1 and file2.  The comparison is 
		done 2 ways.  First all of the addresses defined in file1 
		are compared with fil2, then all of the addresses defined in 
		file2 are compared with file1.  This lets you find out if one
		is a subset of the other.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		ih1 = self.load_ih(file1, opts.pic24)
		ih2 = self.load_ih(file2, opts.pic24)

		ranges1 = extract_ranges(ih1)
		ranges2 = extract_ranges(ih2)

		print "\nFile 1 defined address ranges:"
		for r in ranges1:
			print "[0x%X, 0x%X]" % (r[0], r[1])

		print "\nFile 2 defined address ranges:"
		for r in ranges2:
			print "[0x%X, 0x%X]" % (r[0], r[1])

		mismatch = False
		print "\nComparing ranges defined in file1"
		for start,end in ranges1:
			for i in xrange(start, end+1):
				if ih1[i] != ih2[i]:
					mismatch = True
					print "Mismatch at 0x%X: file1=0x%X, file2=0x%X" % (i, ih1[i], ih2[i])

		if not mismatch:
			print "Ranges matched."

		mismatch = False
		print "\nComparing ranges defined in file2"
		for start,end in ranges2:
			for i in xrange(start, end+1):
				if ih1[i] != ih2[i]:
					mismatch = True
					print "Mismatch at 0x%X: file1=0x%X, file2=0x%X" % (i, ih1[i], ih2[i])

		if not mismatch:
			print "Ranges matched."

	def do_ranges(self, subcmd, opts, hexfile):
		"""${cmd_name}: print the address ranges defined in hex file
		
		${cmd_usage}
		${cmd_option_list}
		"""

		ih = self.load_ih(hexfile)

		valid_addr = map(lambda x:x/2, filter(lambda x: x%2==0, ih.addresses()))
		rstart = valid_addr[0]

		print "\nListing Address Ranges"
		for i in xrange(1, len(valid_addr)):
			if valid_addr[i] != valid_addr[i-1] + 1:
				rend = valid_addr[i-1]
				print "Range: 0x%X-0x%X" % (rstart, rend)

				rstart = valid_addr[i]

		print "Range: 0x%X-0x%X" % (rstart, valid_addr[-1])

	def load_ih(self, hexfile, pic24=False):
		try:
			if not pic24:
				ih = intelhex.IntelHex16bit(hexfile)
			else:
				ih = intelhex.IntelHex(hexfile)
		except IOError as e:
			self.error(str(e))

		ih.padding = 0x3FFF

		return ih

	def parse_instr(self, instr):
		try:
			ins = Instruction(instr)
			return ins
		except ValueError as e:
			self.error(str(e))

	def parse_ranges(self, ranges_str):
		ranges = map(lambda x:x.split('-'), ranges_str)
		ranges = map(lambda x: (int(x[0].lstrip().rstrip(),0), int(x[1].lstrip().rstrip(),0)), ranges)
		ranges = map(lambda x: (x, self._build_range_func(x)), ranges)
		return ranges

	def _build_range_func(self, range):
		def range_func(x):
			if x >= range[0] and x <= range[1]:
				return True

			return False

		return range_func

	def parse_num(self, num):
		return int(num, 0)

	def assert_args(self, opts, args):
		for arg in args:
			if not hasattr(opts, arg) or getattr(opts, arg) is None:
				self.error("You must specify an argument for %s" % arg)

	def error(self, text):
		print Fore.RED + "Error Occurred: " + Style.RESET_ALL + text
		sys.exit(1)

def main():
	hextool = HexTool()
	return hextool.main()