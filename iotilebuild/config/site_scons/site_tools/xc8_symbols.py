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

def build_symbols(target, source, env):
	symtab = symbols.XC8SymbolTable(str(source[0]))
	symtab.generate_h_file(str(target[0]))
	symtab.generate_stb_file(str(target[1]))
	symtab.generate_rom_file(str(target[2]))

_build_sym_h = SCons.Builder.Builder(
	action = build_symbols
	)

def generate(env):
	env['BUILDERS']['build_symbols'] = _build_sym_h

def exists(env):
	return 1

