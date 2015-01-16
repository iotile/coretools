#Automatic building of firmware and unit tests using the
#scons based momo build system

import utilities
import pic24
import pic12
import unit_test
import unit_test12
from SCons.Script import *
import os.path
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pymomo.exceptions import *
import pymomo

def autobuild_pic12(module, test_dir='test', modulefile=None):
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

		Alias('release', os.path.join('build', 'output'))
		Alias('test', os.path.join('build', 'test', 'output'))
		Default('release')
	except MoMoException as e:
		print e.format()
		sys.exit(1)

def autobuild_pic24(module, test_dir='test', modulefile=None, postprocess_hex=None):
	"""
	Build the given pic24 module for all targets.
	"""

	try:
		family = utilities.get_family('mib24', modulefile=modulefile)
		family.for_all_targets(module, lambda x: pic24.build_module(module, x, postprocess_hex=postprocess_hex))

		Alias('release', os.path.join('build', 'output'))
		Alias('test', os.path.join('build', 'test', 'output'))
		Default('release')
	except MoMoException as e:
		print e.format()
		sys.exit(1)
