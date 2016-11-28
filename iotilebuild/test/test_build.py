# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotile.core.utilities import build
from nose.tools import *
import unittest
import os.path
from iotile.core.exceptions import *

def _local_settings():
	folder,last = os.path.split(__file__)
	path = os.path.join(folder, 'test_settings.json')
	return path

def test_loadsettings():
	build.load_settings()

@raises(ArgumentError)
def test_nofile():
	build.load_settings("./Does_not_exist123.hello")

def test_localsettings():
	build.load_settings(_local_settings())

def test_loadfamilies():
	mib12 = build.ChipFamily('mib12', localfile=_local_settings())
	mib24 = build.ChipFamily('mib24', localfile=_local_settings())

@raises(InternalError)
def test_fakefamily():
	build.ChipFamily('mib36')

class TestMIB24Family(unittest.TestCase):
	def setUp(self):
		self.mib24 = build.ChipFamily('mib24', localfile=_local_settings())

	def test_unknown_chip(self):
		with self.assertRaises(ArgumentError):
			self.mib24.find('24f16ka101', 'unknownmodule')

	def test_validate_target(self):
		t1 = "24f16ka101"
		t2 = "24f16ka101/24fj64ga306"
		t3 = "24fj64ga306/test"
		t4 = "24fj64ga306/unknown"
		t5 = "hello"

		eq_(self.mib24.validate_target(t1), True)
		eq_(self.mib24.validate_target(t2), True)
		eq_(self.mib24.validate_target(t3), True)
		eq_(self.mib24.validate_target(t4), False)
		eq_(self.mib24.validate_target(t5), False)

	def test_properties(self):
		target2 = self.mib24.find('24fj64ga306')
		target = self.mib24.find('24fj64ga306/test')

		target.property('defines')
		target.property('unknown', default=None)

		with self.assertRaises(ArgumentError):
			target.property('unknown')

		defs1 = target.property('defines')
		defs2 = target2.property('defines')

		assert defs1['__PIC24FJ64GA306__'] == 1
		assert defs2['__PIC24FJ64GA306__'] == 1
		assert defs1['__TEST__'] == 1

		with self.assertRaises(KeyError):
			a = defs2['__TEST__']

	def test_module_target(self):
		target = self.mib24.find('24fj64ga306/test', 'mainboard')
		target.property('linker')

		with self.assertRaises(ArgumentError):
			self.mib24.find('24fj64ga306/test', 'unknown_module')