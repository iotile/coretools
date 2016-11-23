import json

def convert(arg, **kwargs):
	if arg is None:
		return None

	if isinstance(arg, basestring):
		return json.loads(arg)
	elif isinstance(arg, dict):
		return arg
	
	raise TypeError("Unknown argument type")

def _json_formatter(arg):
	if isinstance(arg, bytearray):
		return repr(arg)

	return str(arg)
	
def default_formatter(arg, **kwargs):
	return json.dumps(arg, sort_keys=True, indent=4, separators=(',', ': '), default=_json_formatter)