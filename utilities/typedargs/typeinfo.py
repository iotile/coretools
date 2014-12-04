#typeinfo.py
#Basic routines for converting information from string or other binary
#formats to python types and for displaying those types in supported 
#formats

from pymomo.exceptions import *
import annotate
import types
import os.path
import imp

def convert_to_type(value, type, **kwargs):
	"""
	Convert value to type 'type'

	If the conversion routine takes various kwargs to 
	modify the conversion process, **kwargs is passed
	through to the underlying conversion function
	"""

	if not is_known_type(type):
		raise ArgumentError("type is not known to type system", type=type)

	typeobj = getattr(types, type)

	conv = typeobj.convert(value, **kwargs)
	return conv

def get_type_size(type):
	"""
	Get the size of this type for converting a hex string to the
	type. Return 0 if the size is not known.
	"""

	if not is_known_type(type):
		raise ArgumentError("type is not known to type system", type=type)

	typeobj = getattr(types, type)

	if hasattr(typeobj, 'size'):
		return typeobj.size()

	return 0

def format_value(value, type, format=None, **kwargs):
	"""
	Convert value to type and format it as a string

	type must be a known type in the type system and format,
	if given, must specify a valid formatting option for the
	specified type.
	"""

	typed_val = convert_to_type(value, type, **kwargs)
	typeobj = getattr(types, type)

	#Allow types to specify default formatting functions as 'default_formatter'
	#otherwise if not format is specified, just convert the value to a string
	if format is None:
		if hasattr(typeobj, 'default_formatter'):
			format_func = getattr(typeobj, 'default_formatter')
			return format_func(typed_val, **kwargs)

		return str(typed_val)

	formatter = "format_%s" % str(format)
	if not hasattr(typeobj, formatter):
		raise ArgumentError("Unknown format for type", type=type, format=format, formatter_function=formatter)

	format_func = getattr(typeobj, formatter)
	return format_func(typed_val, **kwargs)

def is_known_type(type):
	"""
	Check if type is known to the type system.

	Returns boolean indicating if type is known.
	"""

	if not isinstance(type, basestring):
		raise ArgumentError("type must be a string naming a known type", type=type)

	if not hasattr(types, type):
		return False

	return True

def is_known_format(type, format):
	"""
	Check if format is known for given type.

	Returns boolean indicating if format is valid for the specified type.
	"""

	if not is_known_type(type):
		return False

	typeobj = getattr(types, type)
	formatter = "format_%s" % str(format)
	if not hasattr(typeobj, formatter):
		return False

	return True

def inject_type(name, typeobj):
	"""
	Given a module-like object that defines a type, add it to our type system so that
	it can be used with the momo tool and with other annotated API functions.
	"""

	#TODO add checking each type for the minimum required content like a default formatter,
	#a conversion function, etc.

	if is_known_type(name):
		raise ArgumentError("attempting to inject a type that is already defined", type=name)

	setattr(types, name, typeobj)

def load_external_types(path, verbose=False):
	"""
	Given a path to a python package or module, load that module, search for all defined variables
	inside of it that do not start with _ or __ and inject them into the type system.  If any of the
	types cannot be injected, silently ignore them unless verbose is True.  If path points to a module
	it should not contain the trailing .py since this is added automatically by the python import system
	"""

	d,p = os.path.split(path)

	try:
		fileobj,pathname,description = imp.find_module(p, [d])
		mod = imp.load_module(p, fileobj, pathname, description)
	except ImportError:
		raise ArgumentError("could not import module in order to load external types", module_path=path, parent_directory=p, module_name=p)

	for name in filter(lambda x: not x.startswith('_'), dir(mod)):
		typeobj = getattr(mod, name)
		inject_type(name, typeobj)

	#TODO add checking for types that could not be injected and report them
