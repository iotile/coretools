#integer type

def convert(arg):
	if arg is None:
		return None

	if isinstance(arg, basestring):
		return int(arg, 0)
	elif isinstance(arg, int) or isinstance(arg, long):
		return arg
	
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
		raise ValueError("not in required range [%d, %d]" %(int(lower), int(upper)))

#Formatting functions
def format_unsigned(arg, **kwarg):
	return format(arg, 'd')

def format_hex(arg, **kwarg):
	return "0x%X" % arg