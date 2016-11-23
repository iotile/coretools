# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import os.path

def convert(arg):
	if arg is None:
		return None

	return str(arg)

def validate_readable(arg):
	if arg is None:
		raise ValueError("Path must be readable")

	if not os.path.isfile(arg):
		raise ValueError("Path is not a file")

	try:
		f = open(arg, "r")
		f.close()
	except:
		raise ValueError("Path could not be opened for reading")

def validate_exists(arg):
	if arg is None:
		raise ValueError("Path must exist")

	if not os.path.exists(arg):
		raise ValueError("Path must exist")

def validate_writeable(arg):
	if arg is None:
		raise ValueError("Path must be writable")

	parent = os.path.dirname(arg)
	if not os.path.isdir(parent):
		raise ValueError("Parent directory does not exist and path must be writeable")
	
#Formatting functions
def default_formatter(arg, **kwargs):
	return str(arg)