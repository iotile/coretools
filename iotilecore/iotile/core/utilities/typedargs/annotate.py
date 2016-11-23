# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#annotate.py
from decorator import decorator
from iotile.core.exceptions import *
import inspect
from typeinfo import type_system
from collections import namedtuple
import sys

class BasicContext(dict):
	pass

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

	#Ensure that only IOTileException subclasses are passed by the caller
	try:
		retval = f(*convargs, **convkw)
	except IOTileException:
		raise
	except Exception as unknown:
		raise APIError(str(unknown.args)), None, sys.exc_info()[2]

	return retval

def _process_arg(f, arg, value):
	"""
	Ensure that value is a valid argument for the named 
	parameter arg based on the annotated type and validator
	information.  Any errors are raised as either 
	ConversionError or ValidationError exceptions.
	"""

	if arg in f.params:
		val = type_system.convert_to_type(value, f.types[arg])
	else:
		val = value

	#Run all of the validators
	try:
		if arg in f.valids:
			for valid in f.valids[arg]:
				valid[0](val, *valid[1])
	except (ValueError,TypeError) as e:
		raise ValidationError(e.args[0], argument=arg, value=val)

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
			raise ValidationError("Cannot resolve validator", typename=str(type), method_name=name, methods=dir(type))

		func = getattr(type, name)
		outvals.append((func, args))

	return outvals

def get_spec(f):
	if inspect.isclass(f):
		f = f.__init__

	spec = inspect.getargspec(f)

	if spec.defaults is None:
		numreq = len(spec.args)
	else:
		numreq = len(spec.args) - len(spec.defaults)

	#If the first argument is self, don't return it
	start = 0
	if numreq > 0 and spec.args[0] == 'self':
		start = 1

	reqargs = spec.args[start:numreq]
	optargs = set(spec.args[numreq:])

	return reqargs, optargs

def spec_filled(req, opt, pos, kw):
	left = filter(lambda x: x not in kw, pos)
	left = req[len(left):]

	if len(left) == 0:
		return True

	return False

def get_signature(f):
	"""
	Return the pretty signature for this function:
	foobar(type arg, type arg=val, ...)
	"""

	name = f.__name__

	if inspect.isclass(f):
		f = f.__init__

	spec = inspect.getargspec(f)
	num_args = len(spec.args)

	num_def = 0
	if spec.defaults is not None:
		num_def = len(spec.defaults)
	
	num_no_def = num_args - num_def

	args = []
	for i in xrange(0, len(spec.args)):
		typestr = ""
		if i == 0 and spec.args[i] == 'self':
			continue

		if spec.args[i] in f.types:
			typestr = "%s " % f.types[spec.args[i]]

		if i >= num_no_def:
			default = str(spec.defaults[i-num_no_def])
			if len(default) == 0:
				default="''"

			args.append("%s%s=%s" % (typestr, str(spec.args[i]), default))
		else:
			args.append(typestr + str(spec.args[i]))

	return "%s(%s)" % (name, ", ".join(args))

def print_help(f):
	"""
	Print usage information about a context or function.

	For contexts, just print the context name and its docstring
	For functions, print the function signature as well as its
	argument types.
	"""

	if isinstance(f, BasicContext):
		name = context_name(f)

		print "\n" + name + "\n"
		doc = inspect.getdoc(f)
		if doc is not None:
			doc = inspect.cleandoc(doc)
			print doc

		return

	sig = get_signature(f)
	doc = inspect.getdoc(f)
	if doc is not None:
		doc = inspect.cleandoc(doc)

	print "\n" + sig + "\n"
	if doc is not None:
		print doc

	if inspect.isclass(f):
		f = f.__init__

	print "\nArguments:"
	for key in f.params.iterkeys():
		type = f.types[key]
		desc = ""
		if key in f.param_descs:
			desc = f.param_descs[key]

		print " - %s (%s): %s" % (key, type, desc)

def print_retval(f, value):
	if hasattr(f, 'typed_retval') and f.typed_retval == True:
		print type_system.format_return_value(f, value)
		return

	if not hasattr(f, 'retval'):
		print str(value)

	elif f.retval.printer[0] is not None:
		f.retval.printer[0](value)
	elif f.retval.desc != "":
		print "%s: %s" % (f.retval.desc, str(value))

def find_all(container):
	if isinstance(container, dict):
		names = container.keys()
	else:
		names = dir(container)
	
	context = BasicContext()

	for name in names:
		#Ignore _ and __ names
		if name.startswith('_'):
			continue

		if isinstance(container, dict):
			obj = container[name]
		else:
			obj = getattr(container, name)

		#Check if this is an annotated object that should be included.  Check the type of
		#annotated to avoid issues with module imports where someone did from annotate import *
		#into the module causing an annotated symbol to be defined as a decorator
		
		#If we are in a dict context then strings point to lazily loaded modules so include them
		#too.
		if isinstance(container, dict) and isinstance(obj, basestring):
			context[name] = obj
		elif hasattr(obj, 'annotated') and isinstance(getattr(obj, 'annotated'), int):
			context[name] = obj

	return context

def context_from_module(module):
	"""
	Given a module, create a context from all of the top level annotated
	symbols in that module.  
	"""

	con = find_all(module)

	if hasattr(module, "__doc__"):
		setattr(con, "__doc__", module.__doc__)

	if hasattr(module, "_name_"):
		name = module._name_
	else:
		name = module.__name__

	setattr(con, '_annotated_name', name)
	setattr(con, 'context', True)

	con = annotated(con)

	return name, con


def check_returns_data(f):
	if hasattr(f, 'typed_retval') and f.typed_retval == True:
		return True

	if not hasattr(f, 'retval'):
		return False

	return f.retval.data

#Decorators
def param(name, type, *validators, **kwargs):
	def _param(f):
		f = annotated(f)

		f.params[name] = type_system.get_type(type)
		f.types[name] = type
		f.valids[name] = _parse_validators(f.params[name], validators)

		if 'desc' in kwargs:
			f.param_descs[name] = kwargs['desc']

		return decorator(_check_and_execute, f)

	return _param

def returns(desc=None, printer=None, data=True):
	"""
	Specify how the return value of this function should be handled

	If data == True, then this function just returns data and does 
	not return a context so that the context for future calls remains
	unchanged.  
	"""

	def _returns(f):
		annotated(f)

		f.retval = namedtuple("ReturnValue", ["desc", "printer", "data"])
		f.retval.desc = desc
		f.retval.printer = (printer,)
		f.retval.data = data

		return f

	return _returns

def return_type(type, formatter=None):
	"""
	Specify that this function returns a typed value

	type must be a type known to the MoMo type system and formatter
	must be a valid formatter for that type
	"""

	def _returns(f):
		annotated(f)
		f.typed_retval = True
		f.retval_type = type_system.get_type(type)
		f.retval_typename = type
		f.retval_formatter = formatter

		return f

	return _returns

def context(name=None):
	"""
	Declare that a class defines a MoMo context for use with the momo function for discovering
	and using functionality.
	"""

	def _context(cls):
		annotated(cls)
		cls.context = True

		if name is not None:
			cls._annotated_name = name
		else:
			cls._annotated_name = cls.__name__

		return cls

	return _context

def finalizer(f):
	"""
	Indicate that this function destroys the context in which it is invoked, such as a quit method
	on a subprocess or a delete method on an object.
	"""

	f = annotated(f)
	f.finalizer = True
	return f

def context_name(context):
	"""
	Given a context, return its proper name
	"""

	if hasattr(context, "_annotated_name"):
		return context._annotated_name
	elif inspect.isclass(context):
		return context.__class__.__name__

	return str(context)

def takes_cmdline(f):
	f = annotated(f)
	f.takes_cmdline = True

	return f
	
def annotated(f):
	if not hasattr(f, 'params'):
		f.params = {}
	if not hasattr(f, 'valids'):
		f.valids = {}
	if not hasattr(f, 'types'):
		f.types = {}
	if not hasattr(f, 'param_descs'):
		f.param_descs = {}

	f.annotated = True
	f.finalizer = False
	f.takes_cmdline = False
	return f

def short_description(f):
	"""
	Given an object with a docstring, return the first line of the docstring
	"""

	doc = inspect.getdoc(f)
	if doc is not None:
		doc = inspect.cleandoc(doc)
		lines = doc.splitlines()
		return lines[0]

	return ""