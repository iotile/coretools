from SCons.Script import *
from SCons.Environment import Environment
import sys
import platform
import os.path
from pymomo.utilities.paths import MomoPaths
import utilities
import pyparsing
from pymomo.mib.descriptor import MIBDescriptor
import struct
from pymomo.exceptions import BuildError


def build_program(name, chip):
	"""
	Build an ARM cortex executable
	"""

	dirs = chip.build_dirs()

	output_name = '%s.elf' % (chip.output_name(),)
	output_binname = '%s.bin' % (chip.output_name(),)
	patched_name = '%s_patched.elf' % (chip.output_name(),)
	patchfile_name = '%s_patchcommand.txt' % (chip.output_name(),)
	map_name = '%s.map' % (chip.output_name(),)

	VariantDir(dirs['build'], os.path.join('firmware', 'src'), duplicate=0)

	prog_env = setup_environment(chip)
	prog_env['OUTPUT'] = output_name
	prog_env['OUTPUTBIN'] = os.path.join(dirs['build'], output_binname)
	prog_env['PATCHED'] = os.path.join(dirs['build'], patched_name)
	prog_env['PATCH_FILE'] = os.path.join(dirs['build'], patchfile_name)
	prog_env['PATCH_FILENAME'] = patchfile_name
	prog_env['MODULE'] = name

	#Setup specific linker flags for building a program
	##Specify the linker script
	ldscript = utilities.join_path(chip.property('linker'))
	prog_env['LINKFLAGS'].append('-T"%s"' % ldscript)

	##Specify the output map file
	prog_env['LINKFLAGS'].extend(['-Xlinker', '-Map="%s"' % os.path.join(dirs['build'], map_name)])
	Clean(os.path.join(dirs['build'], output_name), [os.path.join(dirs['build'], map_name)])

	#Compile the CDB command definitions
	compile_mib(prog_env)

	#Compile an elf for the firmware image
	objs = SConscript(os.path.join(dirs['build'], 'SConscript'), exports='prog_env')
	outfile = prog_env.Program(os.path.join(dirs['build'], prog_env['OUTPUT']), objs)

	#Create a patched ELF including a proper checksum
	## First create a binary dump of the program flash
	outbin = prog_env.Command(prog_env['OUTPUTBIN'], os.path.join(dirs['build'], prog_env['OUTPUT']), "arm-none-eabi-objcopy -O binary $SOURCES $TARGET")

	## Now create a command file containing the linker command needed to patch the elf
	outhex = prog_env.Command(prog_env['PATCH_FILE'], outbin, action=prog_env.Action(checksum_creation_action, "Generating checksum file"))
	
	## Next relink a new version of the binary using that patch file to define the image checksum
	patch_env = prog_env.Clone()
	patch_env['LINKFLAGS'].append(['-Xlinker', '@%s' % patch_env['PATCH_FILE']])

	patched_file = patch_env.Program(prog_env['PATCHED'], objs)
	patch_env.Depends(patched_file, [os.path.join(dirs['build'], output_name), patch_env['PATCH_FILE']])

	prog_env.Depends(os.path.join(dirs['build'], output_name), [ldscript])

	prog_env.InstallAs(os.path.join(dirs['output'], output_name), os.path.join(dirs['build'], patched_name))
	prog_env.InstallAs(os.path.join(dirs['output'], map_name), os.path.join(dirs['build'], map_name))

	return os.path.join(dirs['output'], output_name)

def build_library(name, chip):
	"""
	Build a static ARM cortex library
	"""

	dirs = chip.build_dirs()

	output_name = '%s.a' % (chip.output_name(),)

	VariantDir(dirs['build'], 'src', duplicate=0)

	library_env = setup_environment(chip)
	library_env['OUTPUT'] = output_name

	SConscript(os.path.join(dirs['build'], 'SConscript'), exports='library_env')

	library_env.InstallAs(os.path.join(dirs['output'], output_name), os.path.join(dirs['build'], output_name))
	return os.path.join(dirs['output'], output_name)

def setup_environment(chip):
	"""
	Setup the SCons environment for compiling arm cortex code
	"""

	#Make sure we never get MSVC settings for windows since that has the wrong command line flags for gcc
	if platform.system() == 'Windows':
		env = Environment(tools=['mingw', 'ldf_compiler'], ENV = os.environ)
	else:
		env = Environment(tools=['default', 'ldf_compiler'], ENV = os.environ)

	env['INCPREFIX'] = '-I"'
	env['INCSUFFIX'] = '"'
	env['CPPPATH'] = chip.includes()
	env['ARCH'] = chip

	#Setup Cross Compiler
	env['CC'] 		= 'arm-none-eabi-gcc'
	env['AS'] 		= 'arm-none-eabi-as'
	env['LINK'] 		= 'arm-none-eabi-gcc'
	env['AR'] 		= 'arm-none-eabi-ar'
	env['RANLIB']	= 'arm-none-eabi-ranlib'

	#Setup Nice Display Strings
	env['CCCOMSTR'] = "Compiling $TARGET"
	env['ARCOMSTR'] = "Building static library $TARGET"
	env['RANLIBCOMSTR'] = "Indexing static library $TARGET"
	env['LINKCOMSTR'] = "Linking $TARGET"

	#Setup Compiler Flags
	env['CCFLAGS'] = chip.combined_properties('cflags')
	env['LINKFLAGS'] = chip.combined_properties('ldflags')
	env['ARFLAGS'].append(chip.combined_properties('arflags')) #There are default ARFLAGS that are necessary to keep

	#Add in compile tile definitions
	defines = utilities.build_defines(chip.property('defines', {}))
	env['CCFLAGS'].append(defines)

	#Setup Target Architecture
	env['CCFLAGS'].append('-mcpu=%s' % chip.property('cpu'))
	env['LINKFLAGS'].append('-mcpu=%s' % chip.property('cpu'))

	#Setup any linked in libraries
	libdirs, libnames = utilities.process_libaries(chip.combined_properties('libraries'), chip)
	env['LIBPATH'] = libdirs
	env['LIBS'] = libnames

	return env

def compile_mib(env, mibname=None, outdir=None):
	"""
	Given a path to a *.mib file, use mibtool to process it and return a command_map.asm file
	return the path to that file.
	"""

	if outdir is None:
		dirs = env["ARCH"].build_dirs()
		outdir = dirs['build']

	if mibname is None: 
		mibname = os.path.join('firmware', 'src', 'cdb', env["MODULE"] + ".cdb")

	cmdmap_c_path = os.path.join(outdir, 'command_map_c.c')
	cmdmap_h_path = os.path.join(outdir, 'command_map_c.h')

	env['MIBFILE'] = '#' + cmdmap_c_path

	return env.Command([cmdmap_c_path, cmdmap_h_path], mibname, action=env.Action(mib_compilation_action, "Compiling MIB definitions"))

def mib_compilation_action(target, source, env):
	"""
	Compile mib file into a .h/.c pair for compilation into an ARM object
	"""

	try:
		d = MIBDescriptor(str(source[0]))
	except pyparsing.ParseException as e:
		raise BuildError("Could not parse mib file", parsing_exception=e, )

	#Build a MIB block from the mib file
	block = d.get_block()
	block.create_c(os.path.dirname(str(target[0])))

def checksum_creation_action(target, source, env):
	"""
	Create a linker command file for patching an application checksum into a firmware image
	"""

	import binascii

	with open(str(source[0]), 'r') as f:
		data = f.read()

		#Ignore the last four bytes of the file since that is where the checksum will go
		data = data[:-4]

		#Make sure the magic number is correct so that we're dealing with an actual firmware image
		magicbin = data[-4:]
		magic, = struct.unpack('<L', magicbin)

		if magic != 0xBAADDAAD:
			raise BuildError("Attempting to patch a file that is not a CDB binary (invalid magic number", actual_magic=magic, desired_magic=0xBAADDAAD)

		#ARM chip seeds the crc32 with a specific value
		checksum = binascii.crc32(data, 0xFFFFFFFF)

	with open(str(target[0]), 'w') as f:
		f.write("--defsym=__image_checksum=%s\n" % hex(checksum))
