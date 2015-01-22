import os.path
import unittest
from pymomo.sim import simulator
from pymomo.utilities.config import ConfigFile
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