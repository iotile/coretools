#reflash.py
#methods to build a mib12_executive reflashing hex file

from pymomo.hex8.ranges import *
from pymomo.hex8.merge import *
from pymomo.hex8.decode import *
from pymomo.hex8.instruction import Instruction
from config12 import MIB12Processor
import math

def build_reflasher(stub, payload, chip):
	"""
	Given two intelhex16 objects specifying the stub and payload files,
	combine them into one object making intelligent choices about offsets
	and sizes based on the chip information.

	Be very verbose so that errors don't get hidden from the user.
	"""

	proc = MIB12Processor.FromChip(chip)
	stub_info = analyze_stub(stub, proc)
	load_info = analyze_payload(payload, proc)

	if load_info['load_size'] > stub_info['max_size']:
		raise ValueError("Payload is too big.  Would exceed chip memory")

	insert_hex(stub, payload, start_addr=stub_info['start'], skip_ranges=stub_info['skip'], payload_size=load_info['load_size'])

	#patch the stub payload size and start
	start_row = stub_info['start'] / proc.row_size
	size_row = load_info['load_size'] / proc.row_size

	start_addr = proc.app_rom[0] + 1
	size_addr = proc.app_rom[0] + 2

	oldret = Instruction('retlw 0')

	if stub[start_addr] != Instruction('retlw 0xAB').encode():
		raise ValueError("Invalid reflashing stub, wrong instruction at start_addr 0x%X" % start_addr)

	if stub[size_addr] != Instruction('retlw 0xCD').encode():
		raise ValueError("Invalid reflashing stub, wrong instruction at size_addr 0x%X" % size_addr)

	start_instr = 'retlw 0x%X' % start_row
	size_instr = 'retlw 0x%X' % size_row

	print "Patching start instruction: %s" % start_instr
	stub[start_addr] = Instruction(start_instr).encode()

	print "Patching size instruction: %s" % size_instr
	stub[size_addr] = Instruction(size_instr).encode()

def extract_reflasher(stub, chip):
	proc = MIB12Processor.FromChip(chip)
	start_instr = proc.app_rom[0] + 1
	size_instr = proc.app_rom[0] + 2

	start_row = decode_retlw(stub, start_instr)
	size_row = decode_retlw(stub, size_instr)

	start_addr = start_row*proc.row_size
	load_size = size_row*proc.row_size

	print "Extracted starting address: 0x%X" % start_addr
	print "Extracted payload size: %d" % load_size

	mib_start = 2048 - proc.row_size
	mib_end = proc.mib_range[1]
	skip = build_range(mib_start, mib_end)

	print "Skipping over: (0x%X, 0x%X)" % (skip[0][0],skip[0][1])

	return extract_hex(stub, start_addr=start_addr, skip_ranges=[skip], payload_size=load_size+32)

def analyze_stub(stub, proc):
	print "\nAnalyzing Stub"
	print "Chip type: ", proc.name

	ranges = extract_ranges(stub)
	mibblock = proc.mib_range

	found_mib = False 
	highest_addr = 0

	print "Defined ranges:"
	for r in ranges:
		if r[0] == mibblock[0] and r[1] == mibblock[1]:
			print "[0x%X-0x%X] <--- MIB Block (skipping)" % (r[0], r[1])
			found_mib = True
		else:
			highest_addr = r[1]
			print "[0x%X-0x%X]" % (r[0], r[1])

	if not found_mib:
		raise ValueError("Could not extract mib_block from stub file. Bailing")

	mib_start = int(math.floor(mibblock[0]/proc.row_size))*proc.row_size
	mib_end = mibblock[1]

	if (highest_addr + 1) % proc.row_size != 0:
		raise ValueError("Stub does not end on a row boundary, cannot insert payload")

	print "Skipping mib row: (0x%X, 0x%X)" % (mib_start, mib_end)
	print "Starting Address for payload: 0x%X" % (highest_addr+1)
	
	skip = build_range(mib_start, mib_end)
	payload_start = highest_addr + 1

	max_size = proc.total_prog_mem - payload_start - proc.row_size #we can fill the entire memory - the mib block row
	print "Maximum payload size: %d words" % max_size

	return {'skip':[skip], 'start':payload_start, 'max_size': max_size} 

def analyze_payload(load, proc):
	print "\nAnalyzing Payload"

	ranges = extract_ranges(load)

	highest_addr = 0

	print "Defined ranges:"
	for r in ranges:
		if r[0] >= (1<<15):
			print "[0x%X-0x%X] <--- Config Words (ignored)" % (r[0], r[1])
		else:
			highest_addr = r[1]
			print "[0x%X-0x%X]" % (r[0], r[1])

	#The actual bootloader is 2 words smaller than the range defined because
	#it includes dummy return instructions for the appcode entry points
	load_size = highest_addr - 2 
	if load_size % proc.row_size != 0:
		raise ValueError("Payload should be a multiple of the flash row size for the chip.")

	print "Payload Size: %d" % load_size

	return {'load_size': load_size}