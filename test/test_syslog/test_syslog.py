# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore import syslog
import unittest
import os.path
from nose.tools import *
from iotilecore.exceptions import *

class TestLogDefinitionMap(unittest.TestCase):
	"""
	Test to make sure the LogDefinitionMap is working correctly
	"""

	def setUp(self):
		self.map = syslog.LogDefinitionMap()

	def test_basic(self):
		pass


	def test_parsing_good(self):
		"""
		Test parsing of a correctly formatted ldf file
		"""

		path = os.path.join(os.path.dirname(__file__), 'log_definitions1.ldf')
		self.map.add_ldf(path)


	@raises(InternalError)
	def test_parsing_syntax_error1(self):
		"""
		Test parsing of an ldf file with a syntax error 1
		"""

		path = os.path.join(os.path.dirname(__file__), 'log_definitions_error1.ldf')
		self.map.add_ldf(path)

	@raises(InternalError)
	def test_parsing_syntax_error2(self):
		"""
		Test parsing of an ldf file with a syntax error 2
		"""

		path = os.path.join(os.path.dirname(__file__), 'log_definitions_error2.ldf')

		try:
			self.map.add_ldf(path)
		except InternalError as e:
			eq_(e.params['line'], "- \"Address\" as integer, format hex")
			raise e

	@raises(InternalError)
	def test_parsing_syntax_error3(self):
		"""
		Test parsing of an ldf file with a semantic error
		"""

		path = os.path.join(os.path.dirname(__file__), 'log_definitions_error3.ldf')

		try:
			self.map.add_ldf(path)
		except InternalError as e:
			eq_(e.params['reason'], "Invalid or missing log message")
			raise e
