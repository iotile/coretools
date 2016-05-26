# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from __future__ import print_function
from decorator import decorator
import traceback
import sys

def deprecated(message=None):
	"""
	Decorator to mark a function as deprecated.  Anytime it is
	called will result in a backtrace being printed with the 
	deprecation message to stderr.
	"""

	if message is None:
		message = "This function has been deprecated."
	if not isinstance(message, basestring):
		message = str(message)

	def _deprecated(f, *args, **kwargs):
		print("Function '%s' has been deprecated" % f.__name__, file=sys.stderr)
		print("Reason: %s" % message, file=sys.stderr)
		print("Callstack follows", file=sys.stderr)
		traceback.print_stack(file=sys.stderr)

		return f(*args, **kwargs)

	def wrap_func(f):
		return decorator(_deprecated, f)

	return wrap_func