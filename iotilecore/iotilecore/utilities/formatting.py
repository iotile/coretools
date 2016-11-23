# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#formatting.py

def indent_block(string_block, level):
	indent = ' '*level
	repstr = '\n' + indent

	retval = string_block.replace('\n', repstr)
	return indent + retval

def indent_list(list, level):
	"""
	Join a list of strings, one per line with 'level' spaces before each one
	"""

	indent = ' '*level
	joinstr = '\n' + indent

	retval = joinstr.join(list)
	return indent + retval