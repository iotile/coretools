def convert(arg):
	if arg is None:
		return None

	return str(arg)

def validate_list(arg, choices):
	"""
	Make sure the argument is in the list of choices passed to the function
	"""
	
	choice_set = set(choices)

	if arg not in choices:
		raise ValueError('Value not in list: %s' % str(choices))