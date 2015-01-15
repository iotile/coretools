#convert.py
#Convert PIC24 hex files into a form that can be programmed for recovery
#Each pic24 instruction is 3 bytes.  XC16 pads this to 4 bytes.  We can't
#have it padded since we need to program it into the device directly

import intelhex as ih

def unpad_pic24_hex(hexfile):
	"""
	Given a pic24 hex file, return an intel hex object that is not padded
	"""

	f = ih.IntelHex(hexfile)
	out = ih.IntelHex()

	i = 0
	j = 0


	if (f.maxaddr() +1) % 4 != 0:
		raise ValueError("Cannot pack PIC24 hex file since its length is not a multiple of 4")

	for i in xrange(0, f.maxaddr()+1, 4):
		out[j+0] = f[i+0]
		out[j+1] = f[i+1]
		out[j+2] = f[i+2]
		j += 3

	return out

def pad_pic24_hex(f):
	out = ih.IntelHex()

	i = 0
	j = 0

	if (f.maxaddr() + 1) % 3 != 0:
		raise ValueError("PIC24 hex file did not have length of a multiple of 3, was not correctly packed.")
	
	for i in xrange(0, f.maxaddr()+1, 3):
		out[j+0] = f[i+0]
		out[j+1] = f[i+1]
		out[j+2] = f[i+2]
		out[j+3] = 0x00

		j += 4

	return out