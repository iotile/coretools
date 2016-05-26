# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.


def parse_args(fmt, args):
	"""
	Parse the argument list according to the passed format string.
	each character in fmt specifies the type of each argument.  Valid 
	choices are:
	i - dec, oct, bin or hex integer with leading decoration to distinguish (8 bit)
	a - integer address (16 bit) 
	"""
	if len(args) != len(fmt):
		raise ValueError("Invalid number of arguments, expected %d from format '%s', received %d." % (len(fmt), fmt, len(args)))

	parsed = []

	for i,c in enumerate(fmt):
		argstr = args[i]

		arg = None

		if c == 'i':
			if isinstance(argstr, basestring):
				arg = int(argstr, 0)
			else:
				arg = int(argstr)

			if arg >= 256:
				raise ValueError("8-bit integer argument too large: %d" % arg)
		elif c == 'a':
			arg = int(argstr, 0)
			if arg >> 16 != 0:
				raise ValueError("16-bit address argument too large: %d" % arg)

		if arg is None:
			raise ValueError("Unknown argument type: %s", c)

		parsed.append(arg)

	return parsed