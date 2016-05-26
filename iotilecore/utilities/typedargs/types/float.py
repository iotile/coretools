# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

def convert(arg):
	if arg is None:
		return None

	if isinstance(arg, basestring) or isinstance(arg, int) or isinstance(arg, long) or isinstance(arg, float):
		return float(arg)
	
	raise TypeError("Unknown argument type")

#Validation Functions
def validate_positive(arg):
	if arg is None:
		return

	if arg <=0:
		raise ValueError("value is not positive")

def validate_nonnegative(arg):
	if arg is None:
		return

	if arg < 0:
		raise ValueError("value is negative")

def validate_range(arg, lower, upper):
	if arg is None:
		return

	if arg < lower or arg > upper:
		raise ValueError("not in required range [%f, %f]" %(float(lower), float(upper)))

#Formatting functions
def default_formatter(arg, **kwarg):
	return str(arg)