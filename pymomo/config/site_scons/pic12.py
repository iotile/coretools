#pic12

from SCons.Script import *
from SCons.Environment import Environment
import os
import fnmatch
import json as json
import sys
import os.path
from copy import deepcopy
import utilities
import pyparsing

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pymomo.utilities import build
from pymomo.mib.config12 import MIB12Processor
from pymomo.mib.descriptor import MIBDescriptor
from pymomo.mib.block import MIBBlock
import pymomo.mib.block

from pymomo.hex8 import patch
from pymomo.utilities import intelhex
from pymomo.exceptions import *


def configure_env_for_xc8(env, **kwargs):
	"""
	Setup all of the environmental varibles that the xc8 Builder needs in order
	to property configure and build an 8-bit module.  There's a lot of sensitve
	magic here!  Getting the RAM and ROM ranges wrong will cause very subtle but
	deadly bugs as the executive and applications begin to overwite each other's
	variables.  Be careful when you modify this function.
	"""
	arch = env['ARCH']
	proc = MIB12Processor('No Name', arch.settings)

	#concatenate cflags
	flags = deepcopy(arch.property('xc8_flags', []))
	flags.extend(arch.property('extra_xc8_flags', []))

	#set up definitions for this chip
	defines = deepcopy(arch.property('defines'))
	defines["kFirstApplicationRow"] = proc.first_app_page
	defines["kApplicationAddress"] = proc.first_app_page*proc.row_size
	defines["kFlashRowSize"] = proc.row_size
	defines["kFlashMemorySize"] = proc.total_prog_mem
	
	#set up includes
	incs = arch.includes()

	#set up generic environment variables that are set for both app and exec
	env['MIB_API_BASE'] = proc.api_range[0]
	env['CHIP'] = proc

	#Let the module type dictate whether we build for app or exec
	if arch.property('is_exec'):
		env['ROMSTART'] = proc.exec_rom[0]
		env['ROMEND'] = proc.exec_rom[1]

		flags += ['-L-Pmibapi=%xh' % env['MIB_API_BASE'], '-L-Papp_vectors=%xh' % proc.app_rom[0]] #Place the MIB api in the right place

		env['RAMEXCLUDE'] =  proc.app_ram
	else:
		exec_range = proc.exec_rom

		env['ROMSTART'] = exec_range[1]+1
		env['ROMEND'] = proc.total_prog_mem - 1  

		#Make sure we don't let the code overlap with the MIB map in high memory
		env['ROMEXCLUDE'] = []

		flags += ['--codeoffset=%x' % (exec_range[1]+1)]

		mibstart = proc.mib_range[0]
		lnk_cmd = '-L-Pmibblock=%xh' % mibstart
		flags += [lnk_cmd]

		#MIB12 Executive takes all ram in first 
		env['RAMEXCLUDE'] = proc.exec_ram
		env['NO_STARTUP'] = True

	env['XC8FLAGS'] = flags
	env['XC8FLAGS'] += utilities.build_defines(defines)
	env['INCLUDE'] = incs

def build_module(name, arch):
	"""
	Configure Scons to build an application module for the 8bit pic microchip archicture indicated in arch_name.
	"""

	dirs = arch.build_dirs()

	builddir = dirs['build']
	VariantDir(builddir, 'src', duplicate=0)

	env = Environment(tools=['xc8_compiler', 'patch_mib12', 'xc8_symbols'], ENV = os.environ)
	env.AppendENVPath('PATH','../../tools/scripts')
	env.AppendENVPath('PATH','../../tools/bin')
	env['ARCH'] = arch
	env['MODULE'] = name

	#Load in all of the xc8 configuration from build_settings
	configure_env_for_xc8(env)
	compile_mib(env)

	Export('env')
	SConscript(os.path.join(builddir, 'SConscript'))

	prods = [os.path.join(dirs['build'], 'mib12_app_module.hex'), os.path.join(dirs['build'], 'mib12_app_module_symbols.h'), os.path.join(dirs['build'], 'mib12_app_module_symbols.stb'), os.path.join(dirs['build'], 'mib12_app_module_rom_summary.txt')]

	#Patch in the correct checksum for this module
	outhex = env.Command(os.path.join(dirs['build'], 'mib12_app_module_checksummed.hex'), prods[0], action=env.Action(checksum_insertion_action, "Patching Application Checksum"))

	hexfile = env.InstallAs(os.path.join(dirs['output'], '%s_%s.hex' % (name, arch.arch_name())), outhex[0])
	symheader = env.InstallAs(os.path.join(dirs['output'], '%s_symbols_%s.h' % (name, arch.arch_name())), prods[1])
	symtable = env.InstallAs(os.path.join(dirs['output'], '%s_symbols_%s.stb' % (name, arch.arch_name())), prods[2])
	romusage = env.InstallAs(os.path.join(dirs['output'], '%s_rom_summary_%s.stb' % (name, arch.arch_name())), prods[3])

def compile_mib(env, mibname=None, outdir=None):
	"""
	Given a path to a *.mib file, use mibtool to process it and return a command_map.asm file
	return the path to that file.
	"""

	if outdir is None:
		dirs = env["ARCH"].build_dirs()
		outdir = dirs['build']

	if mibname is None: 
		mibname = os.path.join('src', 'mib', env["MODULE"] + ".mib")

	cmdmap_path = os.path.join(outdir, 'command_map.asm')

	env['MIBFILE'] = '#' + cmdmap_path

	return env.Command(cmdmap_path, mibname, action=env.Action(mib_compilation_action, "Compiling MIB definitions"))

def mib_compilation_action(target, source, env):
	try:
		d = MIBDescriptor(str(source[0]))
	except pyparsing.ParseException as e:
		raise BuildError("Could not parse mib file", parsing_exception=e, )

	#Build a MIB block from the mib file
	block = d.get_block()
	block.create_asm(os.path.dirname(str(target[0])))

def checksum_insertion_action(target, source, env):
	block = MIBBlock(str(source[0]))

	desired_check = block.app_checksum - block.stored_checksum
	desired_check = (~(desired_check) + 1) & 0xFF

	ih = intelhex.IntelHex16bit(str(source[0]))
	result = patch.patch_retlw(ih, block.base_addr + pymomo.mib.block.checksum_offset, block.stored_checksum, desired_check)

	if result is False:
		raise BuildError("Could not patch checksum, unknown error occurred", hex_file=str(source[0]), mib_block=block)

	ih.write_hex_file(str(target[0]))
