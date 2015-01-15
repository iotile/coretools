#decode.py
#Simple routines for decoding information from pic12 instructions

def decode_goto(ih, addr):
	"""
	Return the address pointed to by the goto instruction at addr.
	Raises an exception if addr is not a goto instruction
	"""

	val = ih[addr]

	if not match_high(val, 0b101, 3):
		raise ValueError("Instruction at 0x%X was not a goto." % addr) 

	return val & ((1 << 11)-1)

def decode_retlw(ih, addr):
	val = ih[addr]

	if not match_high(val, 0b110100, 6):
		raise ValueError("Instruction at 0x%X was not a retlw instruction" % addr)

	return val & 0xFF

def decode_brw(ih, addr):
	val = ih[addr]

	if val != 0b1011:
		raise ValueError("Instruction at 0x%X was not a brw instruction" % addr)

	return True

def decode_string(ih, addr, length):
	string = ""

	for i in xrange(0, length):
		a = addr + i
		string += chr(ih[a] & 0xFF)

	return string 

def decode_table(ih, addr, mapper):
	"""
	Given a jumptable of the form:
	addr:
	BRW
	<instr>
	<instr>
	<instr>
	...

	return an array with mapper(<instr>) values.  Decoding stops after 256 entries
	or when mapper throws an exception
	"""

	decode_brw(ih, addr)

	tab = []

	#Table can be at most 256 entries long
	for i in xrange(0, 256):
		addr += 1
		try:
			tab.append(mapper(ih, addr))
		except ValueError:
			break

	return tab

def match_high(val, mask, num_bits):
	"""
	Return true if the high num_bits bits of val equal mask
	"""

	shift = 14-num_bits
	if shift < 0:
		raise ValueError("num_bits must be >= 0 in match_high, was %d" % num_bits)
	elif shift == 14:
		return True

	val = val >> shift

	return (val == mask)