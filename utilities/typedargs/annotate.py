#annotate.py

from decorator import decorator
from exceptions import ValidationError
import inspect
import types
from collections import namedtuple

def _check_and_execute(f, *args, **kwargs):
	"""
	Check the type of all parameters with type information, converting 
	as appropriate and then execute the function.
	"""

	convargs = []
	spec = inspect.getargspec(f)

	#Convert and validate all arguments
	for i in xrange(0, len(args)):
		arg = spec.args[i]
		val = _process_arg(f, arg, args[i])
		convargs.append(val)

	convkw = {}
	for key, val in kwargs:
		convkw[key] = _process_arg(f, key, val)

	return f(*convargs, **convkw)

def _process_arg(f, arg, value):
	"""
	Ensure that value is a valid argument for the named 
	parameter arg based on the annotated type and validator
	information.  Any errors are raised as either 
	ConversionError or ValidationError exceptions.
	"""

	if arg in f.params:
			val = getattr(f.params[arg], 'convert')(value)
	else:
		val = value

	#Run all of the validators
	try:
		if arg in f.valids:
			for valid in f.valids[arg]:
				valid[0](val, *valid[1])
	except (ValueError,TypeError) as e:
		raise ValidationError(arg, val, e.args[0])

	return val

def _parse_validators(type, valids):
	"""
	Given a list of validator names or n-tuples, map the name to 
	a validation function given the type and return a list of 
	validation function, arguments tuples
	"""

	outvals = []

	for val in valids:
		if isinstance(val, basestring):
			args = []
		elif len(val) > 1:
			args = val[1:]
			val = val[0]
		else:
			raise ValueError("You must pass either a n-tuple or a string to define a validator")

		name = "validate_%s" % str(val)

		if not hasattr(type, name):
			raise AttributeError("Cannot resolve validator")

		func = getattr(type, name)
		outvals.append((func, args))

	return outvals

def get_spec(f):
	spec = inspect.getargspec(f)

	if spec.defaults is None:
		numpos = len(spec.args)
	else:
		numpos = len(spec.args) - len(spec.defaults)

	#If the first argument is self, don't return it
	start = 0
	if numpos > 0 and spec.args[0] == 'self':
		start = 1

	posargs = set(spec.args[1:numpos])
	kwargs = set(spec.args[numpos:])

	return posargs, kwargs

def get_signature(f):
	"""
	Return the pretty signature for this function:
	foobar(type arg, type arg=val, ...)
	"""

	spec = inspect.getargspec(f)
	num_args = len(spec.args)

	num_def = 0
	if spec.defaults is not None:
		num_def = len(spec.defaults)
	
	num_no_def = num_args - num_def

	args = []
	for i in xrange(0, len(spec.args)):
		typestr = ""
		if spec.args[i] in f.types:
			typestr = "%s " % f.types[spec.args[i]]

		if i >= num_no_def:
			default = str(spec.defaults[i-num_no_def])
			if len(default) == 0:
				default="''"

			args.append("%s%s=%s" % (typestr, str(spec.args[i]), default))
		else:
			args.append(typestr + str(spec.args[i]))

	return "%s(%s)" % (f.__name__, ", ".join(args))

def print_help(f):
	sig = get_signature(f)
	doc = inspect.getdoc(f)
	if doc is not None:
		doc = inspect.cleandoc(doc)

	print "\n" + sig + "\n"
	if doc is not None:
		print doc

	print "Arguments:"
	#TODO: Finish printing arguments with descriptions

def print_retval(f, value):
	if f.retval.printer[0] is not None:
		f.retval.printer[0](value)
	elif f.retval.desc != "":
		print "%s: %s" % (f.retval.desc, str(value))

def find_all(container):
	names = dir(container)
	context = {}

	for name in names:
		obj = getattr(container, name)
		if hasattr(obj, 'annotated'):
			context[name] = obj

	return context

def returns_data(f):
	if not hasattr(f, 'retval'):
		return False

	return f.retval.data

#Decorator
def param(name, type, *validators, **kwargs):
	def _param(f):
		if not hasattr(f, 'params'):
			f.params = {}
		if not hasattr(f, 'valids'):
			f.valids = {}
		if not hasattr(f, 'types'):
			f.types = {}

		if not hasattr(types, type):
			raise AttributeError('Unknown parameter type: %s' % str(type))

		f.params[name] = getattr(types, type)
		f.types[name] = type
		f.valids[name] = _parse_validators(f.params[name], validators)
		f.annotated = True

		return decorator(_check_and_execute, f)

	return _param

def returns(desc=None, printer=None, data=False):
	def _returns(f):
		f.retval = namedtuple("ReturnValue", ["desc", "printer", "data"])
		f.retval.desc = desc
		f.retval.printer = (printer,)
		f.retval.data = data

		if not hasattr(f, 'params'):
			f.params = {}
		if not hasattr(f, 'valids'):
			f.valids = {}
		if not hasattr(f, 'types'):
			f.types = {}

		f.annotated = True
		return f

	return _returns

def annotated(f):
	if not hasattr(f, 'params'):
		f.params = {}
	if not hasattr(f, 'valids'):
		f.valids = {}
	if not hasattr(f, 'types'):
		f.types = {}

	f.annotated = True
	return f

