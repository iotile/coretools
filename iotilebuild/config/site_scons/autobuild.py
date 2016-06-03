# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#Automatic building of firmware and unit tests using the
#scons based momo build system

import utilities
import pic24
import pic12
import unit_test
import unit_test12
import unit_test24
from SCons.Script import *
import os.path
import os
import sys
import arm

from iotilecore.exceptions import *
import iotilecore

def autobuild_arm_program(module, family, test_dir=os.path.join('firmware', 'test'), modulefile=None, boardfile=None, jigfile=None, patch=True):
	"""
	Build the an ARM module for all targets and build all unit tests. If pcb files are given, also build those.
	"""

	try:
		family = utilities.get_family(family, modulefile=modulefile)
		family.for_all_targets(module, lambda x: arm.build_program(module, x, patch=patch))
		
		unit_test.build_units(test_dir, family.targets(module))

		if boardfile is not None:
			autobuild_pcb(module, boardfile)
		if jigfile is not None:
			autobuild_pcb(module, jigfile)

		Alias('release', os.path.join('build', 'output'))
		Alias('test', os.path.join('build', 'test', 'output'))
		Default('release')
	except IOTileException as e:
		print e.format()
		sys.exit(1)


def autobuild_pic12(module, test_dir=os.path.join('firmware', 'test'), modulefile=None, boardfile=None, jigfile=None):
	"""
	Build the given module for all targets and build all unit tests.
	targets are determined from /config/build_settings.json using
	the module name and the tests are found automatically and built 
	using their builtin metadata
	"""
	
	try:
		family = utilities.get_family('mib12', modulefile=modulefile)
		family.for_all_targets(module, lambda x: pic12.build_module(module, x))
		
		unit_test.build_units(test_dir, family.targets(module))

		if boardfile is not None:
			autobuild_pcb(module, boardfile)
		if jigfile is not None:
			autobuild_pcb(module, jigfile)

		Alias('release', os.path.join('build', 'output'))
		Alias('test', os.path.join('build', 'test', 'output'))
		Default('release')
	except IOTileException as e:
		print e.format()
		sys.exit(1)

def autobuild_pic24(module, test_dir=os.path.join('firmware', 'test'), modulefile=None, postprocess_hex=None, boardfile=None, jigfile=None):
	"""
	Build the given pic24 module for all targets.
	"""

	try:
		family = utilities.get_family('mib24', modulefile=modulefile)
		family.for_all_targets(module, lambda x: pic24.build_module(module, x, postprocess_hex=postprocess_hex))

		unit_test.build_units(test_dir, family.targets(module))

		if boardfile is not None:
			autobuild_pcb(module, boardfile)
		if jigfile is not None:
			autobuild_pcb(module, jigfile)

		Alias('release', os.path.join('build', 'output'))
		Alias('test', os.path.join('build', 'test', 'output'))

		Default('release')
	except IOTileException as e:
		print e.format()
		sys.exit(1)

def autobuild_pcb(module, boardfile):
	"""
	Generate production CAM, assembly and BOM data for a circuitboard.
	"""

	pcbpath = os.path.join('build', 'output', 'pcb')

	boardpath = os.path.join('#pcb', boardfile)
	env = Environment(tools=["buildpcb"], ENV = os.environ)

	Alias('pcb', pcbpath)

	env.build_pcb(os.path.join(pcbpath, '%s.timestamp' % boardfile), boardpath)
