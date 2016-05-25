# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import unittest
import os.path
from nose.tools import *
from iotilecore.exceptions import *
from iotilebuild.mib.config12 import MIB12Processor
from iotilebuild.build.build import ChipFamily
import json

class TestRAMCalculations(unittest.TestCase):
	"""
	Test to make sure that ram calculations used to divide memory
	between application and executive in PIC12 code works.
	"""

	def setUp(self):
		path = os.path.join(os.path.dirname(__file__), 'build_settings.json')

		self.mib12 = ChipFamily('mib12', localfile=path)
		settings1822 = self.mib12.find('12lf1822')
		settings1823 = self.mib12.find('16lf1823')
		settings1847 = self.mib12.find('16lf1847')

		self.p1822 = MIB12Processor('1822', settings1822.settings)
		self.p1823 = MIB12Processor('1823', settings1823.settings)
		self.p1847 = MIB12Processor('1847', settings1847.settings)

	def test_basic_ram(self):
		"""
		Make sure basic calculations are working
		"""

		print self.p1822.app_ram
		print self.p1822.exec_ram
