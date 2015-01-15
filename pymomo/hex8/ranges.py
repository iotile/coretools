#ranges.py

def extract_ranges(ih):
	"""
	Given an intelhex16bit object, extract all the disjoint ranges of sequential
	addresses that are defined in the object.
	"""
	valid_addr = map(lambda x:x/2, filter(lambda x: x%2==0, ih.addresses()))
	rstart = valid_addr[0]

	ranges = []

	for i in xrange(1, len(valid_addr)):
		if valid_addr[i] != valid_addr[i-1] + 1:
			rend = valid_addr[i-1]
			ranges.append((rstart, rend))
			rstart = valid_addr[i]

	ranges.append((rstart, valid_addr[-1]))

	return ranges

def build_range(start, end):
	r = (start, end)
	return (r, build_range_func(r))

def build_range_func(range):
		def range_func(x):
			if x >= range[0] and x <= range[1]:
				return True

			return False

		return range_func