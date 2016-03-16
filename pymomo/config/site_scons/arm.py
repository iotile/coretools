from SCons.Script import *
from SCons.Environment import Environment
import sys
import os.path
from pymomo.utilities.paths import MomoPaths

def build_library(name, chip):
	"""
	Build a static ARM cortex library
	"""

	dirs = chip.build_dirs()

	output_name = '%s.a' % (chip.output_name(),)

	VariantDir(dirs['build'], 'src', duplicate=0)

	library_env = Environment(tools=['default', 'ldf_compiler'], ENV = os.environ)
	library_env.AppendENVPath('PATH','../../tools/scripts')

	library_env['ARCH'] = chip
	library_env['OUTPUT'] = output_name
	library_env['CPPPATH'] = chip.includes()

	#Setup Cross Compiler
	library_env['CC'] 		= 'arm-none-eabi-gcc'
	library_env['AS'] 		= 'arm-none-eabi-as'
	library_env['LD'] 		= 'arm-none-eabi-gcc'
	library_env['AR'] 		= 'arm-none-eabi-ar'
	library_env['RANLIB']	= 'arm-none-eabi-ranlib'

	#Setup Nice Display Strings
	library_env['CCCOMSTR'] = "Compiling $TARGET"
	library_env['ARCOMSTR'] = "Building static library $TARGET"
	library_env['RANLIBCOMSTR'] = "Indexing static library $TARGET"

	#Setup Compiler Flags
	library_env['CCFLAGS'] = chip.combined_properties('cflags')
	library_env['LDFLAGS'] = chip.combined_properties('ldflags')
	library_env['ARFLAGS'].append(chip.combined_properties('arflags')) #There are default ARFLAGS that are necessary to keep

	#Setup Target Architecture
	library_env['CCFLAGS'].append('-mcpu=%s' % chip.property('cpu'))

	SConscript(os.path.join(dirs['build'], 'SConscript'), exports='library_env')

	libfile = library_env.InstallAs(os.path.join(dirs['output'], output_name), os.path.join(dirs['build'], output_name))
	return os.path.join(dirs['output'], output_name)
