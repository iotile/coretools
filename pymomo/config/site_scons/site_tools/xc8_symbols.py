import SCons.Builder
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from pymomo.hex8 import symbols

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

