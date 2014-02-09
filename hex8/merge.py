#merge.py
#Given two intelhex16bit objects, merge them together with various options

import intelhex

def insert_hex(stub, payload, start_addr, skip_ranges, payload_size):
	addrs = clip_payload(payload, payload_size)

	print "Inserting Hex file [0x%X, 0x%X]" % (addrs[0], addrs[-1])

	curr = start_addr

	if addrs[0] != 0:
		raise ValueError("Payload does not start at address 0.  This is probably not what you meant.")
		
	for i in xrange(addrs[0], addrs[-1]+1):
		curr, inc = clip_ranges(curr, skip_ranges)
		stub[curr] = payload[i]

		curr += 1

def clip_payload(payload, max_size):
	valid_addr = map(lambda x:x/2, filter(lambda x: x%2==0, payload.addresses())) #addresses are reported in bytes rather than words

	if max_size != 0:
		return filter(lambda x: x<max_size, valid_addr)

	return valid_addr

def clip_ranges(addr, ranges):
	"""
	If addr is contained in ranges, which must not be sequential,
	return the first valid address after the range containing addr
	otherwise just return addr unmodified. 
	"""
	for r,fun in ranges:
		if fun(addr):
			return r[1]+1, False

	return addr, True

def extract_hex(stub, start_addr, skip_ranges, payload_size):
	"""
	Given an IntelHex16bit object in stub, extract the contents starting at
	address start_addr and continuing sequentially for a maximum of payload_size
	bytes.  Do not extract the contents of skip_ranges.  The extracted hex file
	will be sequential before and after each skip range, i.e. those addresses 
	will be collapsed to that the last address before the range and the first
	address after the range are adjacent in the extracted file.
	"""

	maxsize = start_addr+payload_size
	if payload_size == 0:
		maxsize = 0

	addrs = clip_payload(stub, maxsize)
	addrs = filter(lambda x: x>=start_addr, addrs)
	addrs = filter(lambda x: clip_ranges(x, skip_ranges)[1]==True, addrs)

	curr = start_addr
	out = intelhex.IntelHex16bit()
	out.fill = 0x3FFF

	for i in xrange(0, len(addrs)):
		out[i] = stub[addrs[i]]

	return out