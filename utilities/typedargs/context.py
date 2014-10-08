from exceptions import *
import annotate
import inspect
from pymomo.utilities.printer import Printer

class MoMoContext:
	"""

	"""

	def __init__(self, funcs, name=None):
		self.name = name
		self.funcs = funcs

	def print_dir(self):
		if self.name is not None:
			print self.name
		else:
			print annotate.self.funcs_name(self.funcs)

		doc = inspect.getdoc(con)
		if doc is not None:
			doc = inspect.cleandoc(doc)
			print "\n" + doc

		print "\nDefined Functions:"

		if isinstance(self.funcs, dict):
			funs = self.funcs.keys()
		else:
			funs = annotate.find_all(self.funcs)

		for fun in funs:
			print " - " + annotate.get_signature(find_function(self.funcs, fun))

		print "\nBuiltin Functions"
		for bi in builtin_help.values():
			print ' - ' + bi

		print ""

	def print_help(self, fname):
		if fname in builtin_help:
			print builtin_help[fname]
			return

		func = find_function(self.funcs, fname)
		annotate.print_help(func)

	def find_function(self, funname):
		func = None
		if isinstance(self.funcs, dict):
			if funname in self.funcs:
				func = self.funcs[funname]
		elif hasattr(self.funcs, funname):
			func = getattr(self.funcs, funname)

		if func is None:
			raise NotFoundError('Cannot find function to invoke', function=funname)

		return func