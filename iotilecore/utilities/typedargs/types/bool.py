# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#bool.py
#Simple boolean type

def convert(arg, **kwargs):
	if arg is None:
		return arg

	if isinstance(arg, basestring):
		comp = arg.lower()
		if comp == 'true':
			return True
		elif comp == 'false':
			return False
		else:
			raise ValueError("Unknown boolean value (should be true or false): %s" % arg)

	return bool(arg)

def default_formatter(arg, **kwargs):
	return str(arg)
