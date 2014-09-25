import os.path
import unittest
from pymomo.sim import simulator
from pymomo.utilities.config import ConfigFile

class TestSIM30BasicFunctionality(unittest.TestCase):
	"""
	Test to make sure the SIM30 pic24 simulator is working
	correctly
	"""

	def setUp(self):
		conf = ConfigFile('settings')
		sim30path = conf['external_tools/sim30']

		if not os.path.exists(sim30path):
			unittest.skip('SIM30 executable not found')
		else:
			self.sim = simulator.Simulator('SIM30')

	def tearDown(self):
		if hasattr(self, 'sim'):
			self.sim.exit()

	def test_basic_functionality(self):
		self.assertTrue(self.sim.ready())