#shell.py
#Given a command line string, attempt to map it to a function and fill in 
#the parameters based on that function's annotated type information.

from exceptions import *
import annotate
import inspect

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

def print_dir(context):
	print annotate.context_name(context)

	doc = inspect.getdoc(context)
	if doc is not None:
		doc = inspect.cleandoc(doc)
		print "\n" + doc
	print "\nAvailable Functions:"

	if isinstance(context, dict):
		funs = context.keys()
	else:
		funs = annotate.find_all(context)
		funs = filter(lambda x: not x.startswith('__'), funs)

	for fun in funs:
		print " - " + annotate.get_signature(find_function(context, fun))

	print ""

def print_help(context, fname):
	func = find_function(context, fname)
	annotate.print_help(func)

def find_function(context, funname):
	func = None
	if isinstance(context, dict):
		if funname in context:
			func = context[funname]
	elif hasattr(context, funname):
		func = getattr(context, funname)

	if func is None:
		raise NotFoundError(funname)

	return func

def invoke(contexts, line):
	"""
	Given a list of command line arguments, attempt
	to find the function being specified and map the passed 
	arguments to that function based on its annotated type
	information 
	"""

	funname = line[0]
	context = contexts[-1]

	#Check if we are asked for help
	if funname == 'help':
		args = line[1:]
		if len(args) == 0:
			print_dir(context)
		elif len(args) == 1:
			print_help(context, args[0])
		else:
			print "Too many arguments:", args
			print "Usage: help [function]"

		return [], True

	func = find_function(context, funname)

	#find out how many position and kw args this function takes
	posset,kwset = annotate.get_spec(func)

	arg_it = (x for x in line[1:])
	kwargs = {}
	posargs = []

	i = 1
	for arg in arg_it:
		if arg.startswith('--'):
			name,val,skip = process_kwarg(arg, arg_it)
			kwargs[name] = val
			i+= skip
		else:
			if len(posargs) == len(posset):
				break

			posargs.append(arg)

		i += 1

	#print "Consumed %d arguments to execute function" % i
	#print "Remaining line:", line[i:]

	val = func(*posargs, **kwargs)
	finished = True

	if annotate.check_returns_data(func):
		annotate.print_retval(func, val)
	else:
		contexts.append(val)
		finished = False

	return line[i:], finished
