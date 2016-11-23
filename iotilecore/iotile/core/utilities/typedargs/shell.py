# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#shell.py
#Given a command line string, attempt to map it to a function and fill in 
#the parameters based on that function's annotated type information.

from iotile.core.exceptions import *
import annotate
import inspect
import shlex
from typeinfo import type_system
from iotile.core.utilities.rcfile import RCFile
import os.path
import platform
import importlib

posix_lex = platform.system() != 'Windows'

builtin_help = {
	'help': "help [function]: print help information about the current context or a function",
	'back': "back: replace the current context with its parent",
	'quit': "quit: quit the momo shell"
}

def process_kwarg(flag, arg_it):
	flag = flag[2:]
	skip = 0

	#Check if of the form name=value
	if '=' in flag:
		name, value = flag.split('=')
	else:
		name = flag
		value = next(arg_it)
		skip = 1

	return name, value, skip

@annotate.param("package", "path", "exists", desc="Path to the python package containing the types")
@annotate.param("module", "string", desc="The name of the submodule to load from package, if applicable")
def import_types(package, module=None):
	"""
	Add externally defined types from a python package or module

	The MoMo type system is built on the typedargs package, which defines what kinds of types
	can be used for function arguments as well as how those types should be displayed and 
	converted from binary representations or strings.  This function allows you to define external
	types in a separate package and import them into the MoMo type system so that they can be used.
	You might want to do this if you have custom firmware objects that you would like to interact with
	or that are returned in a syslog entry, for example.  

	All objects defined in the global namespace of package (if module is None) or package.module if 
	module is specified that define valid types will be imported and can from this point on be used
	just like any primitive type defined in typedargs itself.  Imported types are indistinguishable 
	from primivtive types like string, integer and path.
	"""

	if module is None:
		path = package
	else:
		path = os.path.join(package, module)

	type_system.load_external_types(path)

def print_dir(context):
	doc = inspect.getdoc(context)
	
	print ""
	print annotate.context_name(context)

	if doc is not None:
		doc = inspect.cleandoc(doc)
		print doc
	
	print "\nDefined Functions:"

	if isinstance(context, dict):
		funs = context.keys()
	else:
		funs = annotate.find_all(context)
	
	for fun in funs:
		fun = find_function(context, fun)
		if isinstance(fun, annotate.BasicContext):
			print " - " + fun._annotated_name
		else:
			print " - " + annotate.get_signature(fun)

		if annotate.short_description(fun) != "":
			print "   " + annotate.short_description(fun) + '\n'
		else:
			print ""

	print "\nBuiltin Functions"
	for bi in builtin_help.values():
		print ' - ' + bi

	print ""

def print_help(context, fname):
	if fname in builtin_help:
		print builtin_help[fname]
		return

	func = find_function(context, fname)
	annotate.print_help(func)

def _do_help(context, line):
	args = line[1:]
	if len(args) == 0:
		print_dir(context)
	elif len(args) == 1:
		print_help(context, args[0])
	else:
		print "Too many arguments:", args
		print "Usage: help [function]"

	return [], True

def deferred_add(add_action):
	"""
	Perform a lazy import of a context so that we don't have a huge initial startup time
	loading all of the modules that someone might want even though they probably only 
	will use a few of them.
	"""

	module, sep, obj = add_action.partition(',')

	mod = importlib.import_module(module)
	if obj == "":
		name, con = annotate.context_from_module(mod)
		return con

	if hasattr(mod, obj):
		return getattr(mod, obj)

	raise ArgumentError("Attempted to import nonexistent object from module", module=module, object=obj)

def find_function(context, funname):
	func = None
	if isinstance(context, dict):
		if funname in context:
			func = context[funname]

			#Allowed lazy loading of functions
			if isinstance(func, basestring):
				func = deferred_add(func)
				context[funname] = func
	elif hasattr(context, funname):
		func = getattr(context, funname)

	if func is None:
		raise NotFoundError("Function not found", function=funname)

	return func

@annotate.context("root")
class InitialContext(dict):
	pass

class HierarchicalShell:
	def __init__(self, name, no_rc=False):
		"""
		Create a new HierarchicalShell, optionally loading initialization
		statements from an RCFile based on the passed identifier 'name'.
		"""

		self.name = name
		self.init_commands = {}

		if not no_rc:
			self._load_rc()

		self.root = InitialContext()
		self.contexts = [self.root]

		self.root_add('import_types', import_types)

		#Initialize the root context if required
		self._check_initialize_context()

	def root_update(self, dict_like):
		"""
		Add all of the entries in the dictionary like object dict_like to the root
		context 
		"""

		self.root.update(dict_like)

	def root_add(self, name, value):
		"""
		Add a single function to the root context
		"""

		self.root[name] = value

	def context_name(self):
		"""
		Get the string name of the current context
		"""

		return annotate.context_name(self.contexts[-1])

	def finished(self):
		"""
		If there are no more contexts on the context list, then we cannot execute any
		commands and the shell has finished its useful life.
		"""

		return len(self.contexts) == 0

	def valid_identifiers(self):
		"""
		Return a list of the valid identifiers that can be called given the context that
		we are in.  Callers can use this result to perform autocomplete if they would like.
		"""

		funcs = annotate.find_all(self.contexts[-1]).keys() + builtin_help.keys()
		return funcs

	def _load_rc(self):
		"""
		Load context initialization commands from a configuration file.  The 
		file should have the format:
		[Context1]
		<list of commands>

		[OldContext1.Subcontext1]
		<list of commands>

		where list of commands is a list of lines that are executed using invoke
		whenever a context matching the identifier inside of the brackets is created
		for the first time.  This lets you run custom configuration routines to take 
		care of tiresome initialization calls automatically.
		"""

		rcfile = RCFile(self.name)
		context = None
		cmds = []

		for line in rcfile.contents:
			line = line.strip()

			if len(line) == 0:
				continue

			if line[0] == '[':
				lasti = line.find(']')
				if lasti == -1:
					raise InternalError("Syntax Error in rcfile, missing closing ]", line=line, name=self.name, path=rcfile.path)

				if context is not None:
					self.init_commands[context] = cmds
				
				#Start a new context
				context = line[1:lasti].strip()
				cmds = []
			else:
				#Process a command line
				if context is None:
					raise InternalError("Syntax Error in rcfile, command given before a context was specified", line=line, name=self.name, path=rcfile.path)

				cmds.append(line)

		if context is not None:
			self.init_commands[context] = cmds

	def _check_initialize_context(self):
		"""
		Check if our context matches something that we have initialization commands
		for.  If so, run them to initialize the context before proceeding with other
		commands.
		"""

		path = ".".join([annotate.context_name(x) for x in self.contexts])

		#Make sure we don't clutter up the output with return values from
		#initialization functions
		old_interactive = type_system.interactive
		type_system.interactive = False

		for key,cmds in self.init_commands.iteritems():
			if path.endswith(key):
				for cmd in cmds:
					line = shlex.split(cmd, posix=posix_lex)

					#Automatically remove enclosing double quotes on windows since they are not removed by shlex in nonposix mode
					def remove_quotes(x):
						if len(x) > 0 and x.startswith(("'", '"')) and x[0] == x[-1]:
							return x[1:-1]

						return x

					if not posix_lex:
						line = map(remove_quotes, line)

					self.invoke(line)

		type_system.interactive = old_interactive

	def invoke(self, line):
		"""
		Given a list of command line arguments, attempt to find the function being specified
		and map the passed arguments to that function based on its annotated type information. 
		"""

		funname = line[0]
		context = self.contexts[-1]

		#Check if we are asked for help
		if funname == 'help':
			return _do_help(context, line)
		if funname == 'quit':
			del self.contexts[:]
			return [], True
		if funname == 'back':
			self.contexts.pop()
			return [], True

		func = find_function(context, funname)

		#If this is a context derived from a module or package, just jump to it
		#since there is no initialization function
		if isinstance(func, annotate.BasicContext):
			self.contexts.append(func)
			self._check_initialize_context()
			return line[1:], False

		#find out how many position and kw args this function takes
		posset,kwset = annotate.get_spec(func)

		#If the function wants arguments directly, do not parse them
		if func.takes_cmdline == True:
			val = func(line[1:])
		else:
			arg_it = (x for x in line[1:])
			kwargs = {}
			posargs = []

			i = 1
			for arg in arg_it:
				if arg.startswith('--') or ((arg.startswith('-') and len(arg)==2)):
					name,val,skip = process_kwarg(arg, arg_it)
					kwargs[name] = val
					i+= skip
				else:
					if annotate.spec_filled(posset, kwset, posargs, kwargs):
						break

					posargs.append(arg)

				i += 1

			if not annotate.spec_filled(posset, kwset, posargs, kwargs):
				raise ArgumentError("too few arguments")

			val = func(*posargs, **kwargs)

		#Update our current context if this function destroyed it or returned a new one.
		finished = True

		if func.finalizer == True:
			self.contexts.pop()
		elif val is not None:
			if annotate.check_returns_data(func):
				if type_system.interactive:
					annotate.print_retval(func, val)
			else:
				self.contexts.append(val)
				self._check_initialize_context()
				finished = False

		return line[i:], finished
