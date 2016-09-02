import json

def convert(arg, **kwargs):
	if arg is None:
		return None

	if isinstance(arg, basestring):
		return json.loads(arg)
	elif isinstance(arg, dict):
		return arg
	
	raise TypeError("Unknown argument type")

def default_formatter(arg, **kwargs):
	return json.dumps(arg, sort_keys=True, indent=4, separators=(',', ': '))