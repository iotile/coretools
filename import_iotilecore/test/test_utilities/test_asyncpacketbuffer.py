from nose.tools import *
import unittest
import os.path
import os
from iotilecore.exceptions import *
from iotilecore.utilities.asyncio import AsyncPacketBuffer
import tempfile
import atexit

# Add test data here
packet1 = bytearray([1, 10, 5, 2] + [x for x in xrange(0, 10)])
packet2 = bytearray([1, 10, 1, 3] + [x for x in xrange(10, 20)])
packet3 = bytearray([1, 10, 2, 4] + [x for x in xrange(20, 30)])
packet4 = bytearray([1, 10, 0, 0] + [x for x in xrange(30, 40)])


def length_function(x):
	return x[1]

def open_function(x):
	return open(x, "r+b")

class TestAsyncIO(unittest.TestCase):
	"""
	Test to make sure that AsyncPacketBuffer works
	"""

	def _create_tempfile(self, src=None, contents=None):
		"""
		Create a named temporary file that is a copy of the src file
		and register for it to be deleted at program exit.
		"""
		dst = tempfile.NamedTemporaryFile(delete=False)

		if src is not None:
			with open(src, "r+b") as f:
				shutil.copyfileobj(f, dst)
		elif contents is not None:
			dst.write(contents)

		dst.close()

		atexit.register(os.remove, dst.name)
		return dst.name

	def setUp(self):
		self.file2 = self._create_tempfile(contents=(packet1 + packet2 + packet3 + packet4))
		self.io = AsyncPacketBuffer(open_function, self.file2, 4, length_function)

	def tearDown(self):
		self.io.stop()

	def test_asyncio(self):
		packet = self.io.read_packet()
		assert packet ==  packet1

	@raises(TimeoutError)
	def test_timeout(self):
		packet = self.io.read_packet()
		other_packet = self.io.read_packet(timeout=0.1)
		other_packet = self.io.read_packet(timeout=0.1)
		other_packet = self.io.read_packet(timeout=0.1)
		other_packet = self.io.read_packet(timeout=0.1)
		other_packet = self.io.read_packet(timeout=0.1)

	def test_multiplepackets(self):
		rpacket1 = self.io.read_packet()
		assert packet1 == rpacket1

		rpacket2 = self.io.read_packet()
		assert packet2 == rpacket2

		rpacket3 = self.io.read_packet()
		assert packet3 == rpacket3
		
		rpacket4 = self.io.read_packet()
		assert packet4 == rpacket4
