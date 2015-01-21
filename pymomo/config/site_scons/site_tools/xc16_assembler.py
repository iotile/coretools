#xc16_assembler.py
#SCons Builder Actions for the XC16 PIC assembler

import SCons.Builder
import SCons.Action
import SCons.Scanner
import os.path
import sys
import utilities

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from pymomo.utilities.paths import convert_path

def xc16_generator(source, target, env, for_signature):
	"""
	Create an XC16 command line using the parameter defined in 
	the environment
	"""

	arch = env['ARCH']

	#Build up the command line
	args = ['xc16-gcc']
	args.extend(['-mcpu=%s' % arch.property('chip')])
	args.extend(['-c'])
	args.append(str(source[0]))
	args.extend(['-o %s' % (str(target[0]))])
	args.extend(utilities.build_includes(arch.includes()))
	args.extend(utilities.build_defines(arch.property('defines', default={})))
	args.extend(arch.property('asflags', default=[]))

	return SCons.Action.Action(" ".join(args), 'Assembling %s' % str(source[0]))

_xc16_obj = SCons.Builder.Builder(
	generator = xc16_generator,
	suffix='.o'
	)

def generate(env):
	env['BUILDERS']['xc16_as'] = _xc16_obj

def exists(env):
	return 1