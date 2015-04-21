#decode.py
#Simple routines for decoding information from pic12 instructions
from pymomo.exceptions import *

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

def decode_movwf(ih, addr):
	val = ih[addr]

	if not match_high(val, 0b0000001, 7):
		raise ValueError("Instruction at 0x%X was not a movwf instruction" % addr)

	return val & 0b1111111 # 7 significant low bits are the register address

def decode_return(ih, addr):
	val = ih[addr]

	if val != 0b1000:
		raise ValueError("Instruction at 0x%X was not a return instruction" % addr)

	return True

def decode_brw(ih, addr):
	val = ih[addr]

	if val != 0b1011:
		raise ValueError("Instruction at 0x%X was not a brw instruction" % addr)

	return True

def decode_movlw(ih, addr):
	val = ih[addr]

	if not match_high(val, 0b110000, 6):
		raise ValueError("Instruction at 0x%X was not a movlw instruction" % addr)

	return val & 0xFF

def decode_string(ih, addr, length):
	string = ""

	for i in xrange(0, length):
		a = addr + i
		string += chr(ih[a] & 0xFF)

	return string

def decode_sentinel_table(ih, addr, entry_size, sentinel_value):
	"""
	Given a table of groups of <entry_size> entries, terminated by a group of sentinel_values,
	decode the values and return them

	#Group 1
	<retlw value0>
	<retlw value1>
	...
	<retlw valuen>

	#Group 2
	...

	#Group N 

	#Sentinel 
	retlw sentinel_value
	"""

	table = []

	is_sentinel = False
	while not is_sentinel:
		entries = []

		is_sentinel = True
		for i in xrange(0, entry_size):
			val = decode_retlw(ih, addr + i)
			entries.append(val)

			if val != sentinel_value[i]:
				is_sentinel = False

		if not is_sentinel:
			table.append(entries)

		addr += entry_size

	return table

def decode_fsr0_loader(ih, func_addr):
	"""
	Given the address of a function that loads FSR0 with a certain value,
	decode that value.

	Function must have the form:
	movlw XX
	movwf FSR0L 
	movlw YY
	movwf FSR0H
	return
	"""

	#Make sure it ends with a return
	decode_return(ih, func_addr + 4)

	fsr0l = decode_movwf(ih, func_addr + 1)
	fsr0h = decode_movwf(ih, func_addr + 3)

	val1 = decode_movlw(ih, func_addr + 0)
	val2 = decode_movlw(ih, func_addr + 2)

	if fsr0l != 0x04 or fsr0h != 0x05:
		raise DataError("FSR0 loader function did not have appropriate movwf instructions to FSR0L and FSR0H in the right places")

	return (val2 << 8) | val1

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