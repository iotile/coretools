#ldf_compiler.py
#SCons Builder Action for creating header files from Log Definition Files

import SCons.Builder
import SCons.Action
import os.path
import sys
import utilities

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from pymomo.utilities.paths import convert_path

def ldf_generator(source, target, env, for_signature):
	"""
	Create an command line to drive the LDF compiler using the parameter defined in 
	the environment
	"""

	chip = env['ARCH']
	types = chip.property('type_package', None)

	#If the user has a custom type package import it so that the log file can find all of the
	#types that it needs to process the ldf file into a header.
	if types is None:
		args = ['momo --norc SystemLog LogDefinitionMap']
	else:
		args = ['momo --norc import_types "%s" SystemLog LogDefinitionMap' % types]

	for src in source:
		args.append('add_ldf \"%s\"' % str(src))

	args.append('generate_header \"%s\"' % str(target[0]))
	return SCons.Action.Action(" ".join(args), 'Compiling Log Definitions into %s' % str(target[0]))

_ldf_obj = SCons.Builder.Builder(
	generator = ldf_generator,
	suffix='.h')

def generate(env):
	env['BUILDERS']['ldf_compiler'] = _ldf_obj

def exists(env):
	return 1