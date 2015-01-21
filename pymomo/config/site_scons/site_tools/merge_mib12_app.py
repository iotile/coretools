import SCons.Builder
import utilities
import intelhex

def merge_app(target, source, env):
	"""
	Given two source files, the first being the mib12_executive and the second
	being an application hex, merge the two into a complete application hex
	"""

	chip = env['CHIP']

	exec_end = chip.exec_rom[1]*2

	execfile = intelhex.IntelHex(str(source[0]))
	appfile = intelhex.IntelHex(str(source[1]))

	execfile.merge(appfile[exec_end+2:], overlap='replace')
	execfile.tofile(str(target[0]), format='hex')

_merge_app = SCons.Builder.Builder(
	action = merge_app
	)

def generate(env):
	env['BUILDERS']['merge_mib12_app'] = _merge_app

def exists(env):
	return 1

