import unittest
import pytest
import os.path
import os
from iotile.mock.mock_iotile import MockIOTileDevice

class TestHardwareManager(unittest.TestCase):
	def setUp(self):
		self.dev = MockIOTileDevice(0, 'TestCN')

	def tearDown(self):
		pass

	def test_calling_rpc(self):
		"""Make sure calling an RPC works at its most basic level
		"""

		print self.dev._rpc_handlers.keys()
		name = self.dev.call_rpc(0x08, 0x0004)
		assert name == 'TestCN'
