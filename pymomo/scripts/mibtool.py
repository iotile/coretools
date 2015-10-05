#!/usr/bin/env python

import sys
import os.path
import os
from pymomo.utilities import intelhex

from pymomo.proteus.project import Project
from pymomo.mib.descriptor import MIBDescriptor
from pymomo.mib.block import MIBBlock
from pymomo.mib.api import MIBAPI
from pymomo.mib import config12
from pymomo.mib.reflash import *
from pymomo.utilities import build
from pymomo.utilities.paths import MomoPaths
import cmdln
from colorama import Fore, Style
import pyparsing

class MIBTool(cmdln.Cmdln):
	name = 'mibtool'

	@cmdln.option('-o', '--output', action='store',  help='Output .pdsprj file to create (without extension)')
	@cmdln.option('-t', '--template', action='store', help='Template project with a Pic24F16KA101 firmware project defined')
	@cmdln.option('-p', '--proc', action='store', default='pic24', choices=['pic24', 'pic12'], help="Processor type choose from pic24 or pic12")
	def do_proteus(self, subcmd, opts, project):
		"""${cmd_name}: Generate a proteus vsm project for this board file.

		Create a Proteus VSM 8 project file, copying all of the source files in 
		to the project file and setting the parameters appropriately for the 
		project to compile out of the box in VSM.  A template project file is 
		required so that we can copy the appropriate settings into the created 
		project file.  It should be an empty project created by Proteus VSM 
		with the correct processor type and a firmware project created with 
		no files added.  If any files are present they will be overwritten.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['template', 'output'])

		if not os.path.exists(opts.template):
			self.error("template project %s does not exist" % opts.template)

		if not os.path.isdir(project):
			self.error("You must pass a directory to mibtool proteus <project directory>")

		proj = Project([project], opts.proc, opts.template)
		proj.create(opts.output)

	def do_build(self, argv):
		"""${cmd_name}: Build the mib12 project in the current directory
		
		${cmd_usage}
		${cmd_option_list}
		"""

		import pymomo.utilities.invoke
		import SCons.Script

		site_path = os.path.abspath(os.path.join(MoMoPaths().base, 'tools', 'site_scons'))


		all_args = ['mibtool', '--site-dir=%s' % site_path]
		sys.argv = all_args + list(argv[1:])
		SCons.Script.main()

	def do_mib12(self, subcmd, opts, name):
		"""${cmd_name}: Create an empty mib12 application module project

		Create a mib12 application module with the given name.  It will
		apeaar in the momo_modules directory with starter files and a
		default empty endpoint file

		name should have no spaces in it.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		fillvars = {
		'module' : {
			'name': name
		}}

		template = RecursiveTemplate('mib12_module', rename=name)
		template.add(fillvars)
		template.render(output_dir=MomoPaths().modules)

		path = os.path.join(MomoPaths().modules, name)
		print "Created mib12 module named %s at:\n%s" % (name, path)

	@cmdln.option('-c', '--chip', help="Chip type that this reflasher corresponds to")
	@cmdln.option('-o', '--output', help="output hex file to create")
	def do_build_reflash(self, subcmd, opts, stub_file, payload_file):
		"""${cmd_name}: build an application module for reflashing the mib12_executive

		Given a mib12_reflash stub hex file and a new version of the mib12_executive,
		combine them into an application module that will reflash the executive onto
		the chip type passed.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['chip', 'output'])

		stub = self.load_ih(stub_file)
		payload = self.load_ih(payload_file)
		chip = opts.chip

		build_reflasher(stub, payload, chip)

		stub.write_hex_file(opts.output)

	@cmdln.option('-c', '--chip', help="Chip type that this reflasher corresponds to")
	@cmdln.option('-o', '--output', help="output hex file to create")
	def do_extract_exec(self, subcmd, opts, stub_file):
		"""${cmd_name}: extract the mib12_executive from a reflash module

		Given a mib12_reflash hex file with a payload, extract that payload and
		save it into output.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['chip', 'output'])

		stub = self.load_ih(stub_file)
		chip = opts.chip

		load = extract_reflasher(stub, chip)
		load.write_hex_file(opts.output)

	@cmdln.option('-o', '--output', action='store', default=None, help="Output direcory to place the command_map.asm file in")
	def do_gen(self, subcmd, opts, mibfile):
		"""${cmd_name}: Compile a .mib file into command_map.asm

		Create a command_map.asm file specifying information about this mib 
		application module by compiling the *.mib file passed in.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		try:
			d = MIBDescriptor(mibfile)
		except pyparsing.ParseException as e:
			self.error(str(e))

		if opts.output is None:
			self.error("You must specify an output directory")
		if not os.path.isdir(opts.output):
			self.error("Invalid output directory specified")

		d.get_block().create_asm(opts.output)

	def do_checksum(self, subcmd, opts, hexfile):
		"""${cmd_name}: Compute an 8-bit checksum for the mib12 app module

		The application module must have a valid mib block so that we can 
		extract the hw type in order to properly calculate where to start 
		computing the checksum.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		#Load the chip type from the mib block and use that to extract the application
		#rom range.
		try:
			b = MIBBlock(hexfile)
		except:
			self.error(str(sys.exc_info()[1]))

		print "\nChecksum:"
		print "hex: 0x%X" % b.app_checksum
		print "dec: %d" % b.app_checksum
		print "bin: %s" % bin(b.app_checksum)

	def do_dump(self, subcmd, opts, hexfile):
		"""${cmd_name}: Dump the MIB Block from a hex file and verify it.

		Given a hex file that should be a valid MIB12 application module, dump 
		the MIB Block, validate the information stored in it and dump it to 
		stdout.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		try:
			b = MIBBlock(hexfile)
			print str(b)
		except:
			self.error(str(sys.exc_info()[1]))

	@cmdln.option('-c', '--chip', help="Chip type that this hex file corresponds to")
	def do_api(self, subcmd, opts, hexfile):
		"""${cmd_name}: Dump the MIB API region from the hex file and verify it 

		Given a hex file that should be a valid MIB12 executive module, 
		validate the information stored in it and dump it to stdout.
		
		${cmd_usage}
		${cmd_option_list}
		"""

		self.assert_args(opts, ['chip'])

		try:
			print "\nDumping file: %s" % hexfile
			api = MIBAPI(hexfile, opts.chip)
			api.print_api()
		except:
			self.error(str(sys.exc_info()[1]))

	def load_ih(self, hexfile):
		try:
			ih = intelhex.IntelHex16bit(hexfile)
		except IOError as e:
			self.error(str(e))

		ih.padding = 0x3FFF

		return ih

	def assert_args(self, opts, args):
		for arg in args:
			if not hasattr(opts, arg) or getattr(opts, arg) is None:
				self.error("You must specify an argument for %s" % arg)

	def error(self, text):
		print Fore.RED + "Error Occurred: " + Style.RESET_ALL + text
		sys.exit(1)

def main():
	mibtool = MIBTool()
	return mibtool.main()