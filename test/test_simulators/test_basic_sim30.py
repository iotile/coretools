import os.path
import unittest
from pymomo.sim import simulator
from pymomo.utilities.config import ConfigFile
from distutils.spawn import find_executable

class TestSIM30BasicFunctionality(unittest.TestCase):
	"""
	Test to make sure the SIM30 pic24 simulator is working
	correctly
	"""

	def setUp(self):
		sim30path = find_executable("sim30")

		if not os.path.exists(sim30path):
			unittest.skip('SIM30 executable not found')
		else:
			self.sim = simulator.Simulator('pic24')

	def tearDown(self):
		if hasattr(self, 'sim'):
			self.sim.exit()

	def test_basic_functionality(self):
		self.assertTrue(self.sim.ready())