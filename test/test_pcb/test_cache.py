import unittest
import os.path
from nose.tools import *
from pymomo.exceptions import *
from pymomo.pcb.partcache import PartCache
import tempfile
import shutil
import atexit

class TestCache(unittest.TestCase):
	"""
	Test to make sure that caching of part request responses is working.
	"""

	def _create_tempfile(self, src=None):
		"""
		Create a named temporary file that is a copy of the src file
		and register for it to be deleted at program exit.
		"""
		dst = tempfile.NamedTemporaryFile(delete=False)

		if src is not None:
			with open(src, "r+b") as f:
				shutil.copyfileobj(f, dst)

		dst.close()

		atexit.register(os.remove, dst.name)
		return dst.name

	def setUp(self):
		self.filled_cachefile = self._create_tempfile(os.path.join(os.path.dirname(__file__), 'eagle', 'pcb_part_cache.db'))
		self.empty_cachefile = self._create_tempfile()

	def test_create_cache(self):
		pc = PartCache(cache=self.empty_cachefile)

		assert pc.size() == 0

		val = {'test':'test', 'hello': 2}
		pc.set('hello', val)
		assert pc.size() == 1

		stored = pc.get('hello')
		assert val == stored

	def test_expire_parts(self):
		"""
		Make sure parts are expired like they should be
		"""

		pc1 = PartCache(cache=self.filled_cachefile, no_expire=True)
		assert pc1.size() > 0

		pc2 = PartCache(cache=self.filled_cachefile, no_expire=False, expiration=1)
		assert pc2.size() == 0
