#bytes.py
#Simple bytearray type

def convert(arg, **kwargs):
	if isinstance(arg, bytearray):
		return arg
	elif isinstance(arg, basestring):
		if len(arg) > 2 and arg.startswith("0x"):
			data = arg[2:].decode('hex')
		else:
			data = arg
		return bytearray(data)

	raise TypeError("You must create a bytes object from a bytearray or a hex string")

def convert_binary(arg, **kwargs):
	return bytearray(arg)

def default_formatter(arg, **kwargs):
	return str(arg)

def format_repr(arg):
	return repr(arg)