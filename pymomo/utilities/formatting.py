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