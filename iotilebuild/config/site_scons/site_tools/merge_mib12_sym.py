# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import SCons.Builder

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from iotilecore.hex8 import symbols

def merge_sym(target, source, env):
	"""
	Given two source files, the first being the mib12_executive and the second
	being an application hex, merge the two into a complete application hex
	"""

	first = symbols.XC8SymbolTable(str(source[0]))

	first.merge(str(source[1]))
	first.generate_stb_file(str(target[0]))

_merge_sym = SCons.Builder.Builder(
	action = merge_sym
	)

def generate(env):
	env['BUILDERS']['merge_mib12_symbols'] = _merge_sym

def exists(env):
	return 1
