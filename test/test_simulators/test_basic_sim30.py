# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import os.path
import unittest
from iotilecore.sim import simulator
from iotilecore.utilities.config import ConfigFile
from distutils.spawn import find_executable

@unittest.skipIf(find_executable("sim30") == None, 'SIM30 executable not found')
class TestSIM30BasicFunctionality(unittest.TestCase):
	"""
	Test to make sure the SIM30 pic24 simulator is working
	correctly
	"""
	def setUp(self):
		self.sim = simulator.Simulator('pic24')

	def tearDown(self):
		self.sim.exit()

	def test_basic_functionality(self):
		self.assertTrue(self.sim.ready())