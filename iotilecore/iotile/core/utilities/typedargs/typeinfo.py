# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#typeinfo.py
#Basic routines for converting information from string or other binary
#formats to python types and for displaying those types in supported 
#formats
#TODO: 
#- Extend the type system to use a recursive parser to allow complex
#  types to be built from other complex types.

import pkg_resources
from iotile.core.exceptions import *
import types
import os.path
import imp

#Start working on recursive parser
#import pyparsing
#symbolchars = pyparsing.Regex('[_a-zA-Z][_a-zA-Z0-9]*')
#typename = pyparsing.Word(symbolchars)

#simpletype = typename
#complextype = pyparsing.Forward()

#typelist = pyparsing.delimitedList(simpletype | complextype, ',')
#complextype << typename + pyparsing.Literal('(').suppress() + typelist + pyparsing.Literal(')').suppress()

#statement = 

class TypeSystem(object):
	"""
	TypeSystem permits the inspection of defined types and supports
	converted string and binary values to and from these types.
	"""

	def __init__(self, *args):
		"""
		Create a TypeSystem by importing all of the types defined in modules passed
		as arguments to this function.  Each module is imported using 
		"""

		self.interactive = False
		self.known_types = {}
		self.type_factories = {}

		for arg in args:
			self.load_type_module(arg)

	def convert_to_type(self, value, type, **kwargs):
		"""
		Convert value to type 'type'

		If the conversion routine takes various kwargs to 
		modify the conversion process, **kwargs is passed
		through to the underlying conversion function
		"""

		if isinstance(value, bytearray):
			return self.convert_from_binary(value, type, **kwargs)

		typeobj = self.get_type(type)

		conv = typeobj.convert(value, **kwargs)
		return conv

	def convert_from_binary(self, binvalue, type, **kwargs):
		"""
		Convert binary data to type 'type'.

		'type' must have a convert_binary function.  If 'type'
		supports size checking, the size function is called to ensure
		that binvalue is the correct size for deserialization  
		"""

		size = self.get_type_size(type)
		if size > 0 and len(binvalue) != size:
			raise ArgumentError("Could not convert type from binary since the data was not the correct size", required_size=size, actual_size=len(binvalue), type=type)

		typeobj = self.get_type(type)

		if not hasattr(typeobj, 'convert_binary'):
			raise ArgumentError("Type does not support conversion from binary", type=type)

		return typeobj.convert_binary(binvalue, **kwargs)

	def get_type_size(self, type):
		"""
		Get the size of this type for converting a hex string to the
		type. Return 0 if the size is not known.
		"""

		typeobj = self.get_type(type)

		if hasattr(typeobj, 'size'):
			return typeobj.size()

		return 0

	def format_value(self, value, type, format=None, **kwargs):
		"""
		Convert value to type and format it as a string

		type must be a known type in the type system and format,
		if given, must specify a valid formatting option for the
		specified type.
		"""

		typed_val = self.convert_to_type(value, type, **kwargs)
		typeobj = self.get_type(type)

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

	def _validate_type(self, typeobj):
		"""
		Validate that all required type methods are implemented.

		At minimum a type must have:
		- a convert() or convert_binary() function
		- a default_formatter() function

		Raises an ArgumentError if the type is not valid
		"""

		if not (hasattr(typeobj, "convert") or hasattr(typeobj, "convert_binary")):
			raise ArgumentError("type is invalid, does not have convert or convert_binary function", type=typeobj, methods=dir(typeobj))

		if not hasattr(typeobj, "default_formatter"):
			raise ArgumentError("type is invalid, does not have default_formatter function", type=typeobj, methods=dir(typeobj))

	def is_known_type(self, type):
		"""
		Check if type is known to the type system.

		Returns boolean indicating if type is known.
		"""

		if not isinstance(type, basestring):
			raise ArgumentError("type must be a string naming a known type", type=type)

		if type in self.known_types:
			return True

		return False

	def split_type(self, typename):
		"""
		Given a potentially complex type, split it into its base type and specializers
		"""

		name = self._canonicalize_type(typename)
		if '(' not in name:
			return name, False, []

		base,sub = name.split('(')
		if len(sub) == 0 or sub[-1] != ')':
			raise ArgumentError("syntax error in complex type, no matching ) found", passed_type=typename, basetype=base, subtype_string=sub)
		
		sub = sub[:-1]

		subs = sub.split(',')
		return base, True, subs

	def instantiate_type(self, typename, base, subtypes):
		"""
		Instantiate a complex type
		"""

		if base not in self.type_factories:
			raise ArgumentError("unknown complex base type specified", passed_type=typename, base_type=base)

		BaseType = self.type_factories[base]

		#Make sure all of the subtypes are valid
		for s in subtypes:
			try:
				self.get_type(s)
			except IOTileException as e:
				raise ArgumentError("could not instantiate subtype for complex type", passed_type=typename, sub_type=s, error=e)

		typeobj = BaseType.Build(*subtypes, type_system=self)
		self.inject_type(typename, typeobj)

	def _canonicalize_type(self, typename):
		return typename.replace(' ', '')

	def get_type(self, typename):
		"""
		Return the type object corresponding to a type name.
		"""

		typename = self._canonicalize_type(typename)

		type, is_complex, subtypes = self.split_type(typename)
		if not self.is_known_type(typename):
			if is_complex:
				self.instantiate_type(typename, type, subtypes)
			else:
				raise ArgumentError("get_type called on unknown type", type=typename)

		return self.known_types[typename]

	def is_known_format(self, type, format):
		"""
		Check if format is known for given type.

		Returns boolean indicating if format is valid for the specified type.
		"""

		typeobj = self.get_type(type)

		formatter = "format_%s" % str(format)
		if not hasattr(typeobj, formatter):
			return False

		return True

	def _is_factory(self, typeobj):
		"""
		Determine if typeobj is a factory for producing complex types
		"""

		if hasattr(typeobj, 'Build'):
			return True

		return False

	def format_return_value(self, function, value):
		"""
		Format the return value of a function based on the annotated type information
		"""

		return self.format_value(value, function.retval_typename, function.retval_formatter)

	def inject_type(self, name, typeobj):
		"""
		Given a module-like object that defines a type, add it to our type system so that
		it can be used with the iotile tool and with other annotated API functions.
		"""

		name = self._canonicalize_type(name)
		base,is_complex,subs = self.split_type(name)

		if self.is_known_type(name):
			raise ArgumentError("attempting to inject a type that is already defined", type=name)

		if (not is_complex) and self._is_factory(typeobj):
			if name in self.type_factories:
				raise ArgumentError("attempted to inject a complex type factory that is already defined", type=name)
			self.type_factories[name] = typeobj
		else:
			self._validate_type(typeobj)
			self.known_types[name] = typeobj

		if not hasattr(typeobj, "default_formatter"):
			raise ArgumentError("type is invalid, does not have default_formatter function", type=typeobj, methods=dir(typeobj))

	def load_type_module(self, module, verbose=False):
		"""
		Given a module that contains a list of some types find all symbols in the module that 
		do not start with _ and attempt to import them as types.
		"""

		for name in filter(lambda x: not x.startswith('_'), dir(module)):
			typeobj = getattr(module, name)

			try:
				self.inject_type(name, typeobj)
			except ArgumentError:
				pass

	def load_external_types(self, path, verbose=False):
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
		except ImportError as e:
			raise ArgumentError("could not import module in order to load external types", module_path=path, parent_directory=d, module_name=p, error=str(e))

		self.load_type_module(mod, verbose)

		#TODO add checking for types that could not be injected and report them

	def load_all_components(self):
		"""
		Allow all registered iotile components that have associated type libraries to 
		add themselves to the global type system.
		"""

		# Find all of the registered IOTile components and see if we need to add any type libraries for them
		from iotile.core.dev.registry import ComponentRegistry

		reg = ComponentRegistry()
		modules = reg.list_components()

		typelibs = reduce(lambda x,y: x+y, [reg.find_component(x).type_packages() for x in modules], [])
		for lib in typelibs:
			if lib.endswith('.py'):
				lib = lib[:-2]

			self.load_external_types(lib)

		#Also search through install distributions for type libraries
		for entry in pkg_resources.iter_entry_points('iotile.type_package'):
			mod = entry.load()
			self.load_type_module(mod) 


#In order to support function annotations that must be resolved to types when modules
#are imported, create a default TypeSystem object that is used globally to store type
#information

type_system = TypeSystem(types)

#Allow iotile plugins to register themselves and include their types
type_system.load_all_components()

def iprint(stringable):
	"""
	A simple function to only print text if in an interactive session.
	"""

	if type_system.interactive:
		print str(stringable)
